"""Bracket generation and private participant/admin read endpoints."""

from collections.abc import Mapping

from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.accounts.models import User
from backend.apps.accounts.permissions import IsApplicationAdmin
from backend.apps.competition.domain.bracket import BracketInputError
from backend.apps.competition.models import Match
from backend.apps.competition.serializers import TournamentBracketSerializer
from backend.apps.competition.services import BracketPersistenceError, generate_bracket
from backend.apps.tournaments.models import Tournament, TournamentParticipant
from backend.apps.tournaments.services import RosterMutationError


class BracketRequestError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "bracket_conflict"

    def __init__(self, error):
        self.status_code = getattr(error, "status_code", self.status_code)
        self.default_code = getattr(error, "code", self.default_code)
        super().__init__(detail=str(error), code=self.default_code)


class BracketReadPermission(BasePermission):
    message = "Нужна активная учётная запись участника или администратора."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role in (User.Roles.ADMIN, User.Roles.PARTICIPANT)
        )


class GenerateBracketRequestSerializer(serializers.Serializer):
    seeding_mode = serializers.ChoiceField(choices=("manual",))

    def to_internal_value(self, data):
        if not isinstance(data, Mapping) or set(data) != {"seeding_mode"}:
            raise ValidationError(
                {"seeding_mode": "Укажите единственное поле seedingMode=manual."}
            )
        return super().to_internal_value(data)


def bracket_payload(tournament: Tournament, matches: list[Match]) -> dict:
    participant_count = TournamentParticipant.objects.filter(
        tournament_id=tournament.pk,
        status=TournamentParticipant.Status.ACTIVE,
    ).count()
    return TournamentBracketSerializer(
        {
            "tournament_id": tournament.pk,
            "roster_frozen_at": tournament.roster_frozen_at,
            "bracket_size": 1 << (participant_count - 1).bit_length(),
            "matches": matches,
        }
    ).data


def bracket_match_queryset():
    return (
        Match.objects.select_related("winner__user", "next_match")
        .prefetch_related(
            "slots__upstream_match",
            "slots__participant__user",
        )
        .order_by("round_index", "position", "id")
    )


@method_decorator(csrf_protect, name="dispatch")
class GenerateBracketView(APIView):
    permission_classes = [IsApplicationAdmin]

    def post(self, request, tournament_id):
        request_serializer = GenerateBracketRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        tournament = get_object_or_404(Tournament, pk=tournament_id)
        try:
            generate_bracket(tournament.pk)
        except (RosterMutationError, BracketInputError, BracketPersistenceError) as error:
            raise BracketRequestError(error) from error

        tournament.refresh_from_db(fields=("roster_frozen_at",))
        matches = bracket_match_queryset().filter(tournament_id=tournament.pk)
        response = Response(
            bracket_payload(tournament, list(matches)), status=status.HTTP_200_OK
        )
        response["Cache-Control"] = "no-store"
        return response


class TournamentBracketView(APIView):
    permission_classes = [BracketReadPermission]

    def get_tournament(self, tournament_id):
        queryset = Tournament.objects.all()
        if self.request.user.role != User.Roles.ADMIN:
            queryset = queryset.filter(
                participants__user=self.request.user,
                participants__status=TournamentParticipant.Status.ACTIVE,
            )
        return get_object_or_404(queryset, pk=tournament_id)

    def get(self, request, tournament_id):
        tournament = self.get_tournament(tournament_id)
        matches = list(bracket_match_queryset().filter(tournament_id=tournament.pk))
        if not matches:
            raise NotFound("Сетка турнира ещё не создана.")
        response = Response(bracket_payload(tournament, matches))
        response["Cache-Control"] = "no-store"
        return response
