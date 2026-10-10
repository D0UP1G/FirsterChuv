"""Bracket generation and private participant/admin read endpoints."""

from collections.abc import Mapping

from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.accounts.models import User
from backend.apps.accounts.permissions import IsApplicationAdmin
from backend.apps.competition.bracket_commands import (
    BracketCommandInputError,
    BracketCommandIdempotencyConflict,
    execute_bracket_command,
)
from backend.apps.competition.domain.bracket import BracketInputError
from backend.apps.competition.domain.admin_actions import AdminAction
from backend.apps.competition.admin_runtime import (
    AdminCommandPersistenceError,
    execute_match_admin_command,
)
from backend.apps.competition.match_api import MatchProjectionError, match_view_payload
from backend.apps.competition.models import Match, MatchSlot
from backend.apps.competition.runtime import (
    MatchRuntimeError,
    configure_match_run,
    start_match_run,
)
from backend.apps.competition.serializers import (
    StrictEmptyObjectSerializer,
    StrictMatchConfigRequestSerializer,
    TournamentBracketSerializer,
)
from backend.apps.competition.services import (
    BracketPersistenceError,
    generate_bracket,
    reset_bracket,
    set_first_round_pairings,
)
from backend.apps.tournaments.models import Tournament, TournamentParticipant
from backend.apps.tournaments.services import RosterMutationError
from backend.apps.problems.catalog import DjangoProblemCatalog


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


class MatchReadPermission(BasePermission):
    message = "Нужен admin или участник этого матча."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role in (User.Roles.ADMIN, User.Roles.PARTICIPANT)
        )


class MatchRequestError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "match_runtime_conflict"

    def __init__(self, message, *, code="match_runtime_conflict", status_code=None):
        if status_code is not None:
            self.status_code = status_code
        self.default_code = code
        super().__init__(detail=message, code=code)


def _require_match_idempotency_key(request):
    key = request.headers.get("Idempotency-Key")
    if not key or len(key) > 200:
        raise ValidationError(
            {"Idempotency-Key": "Укажите непустой ключ длиной не более 200 символов."}
        )
    return key


def _runtime_scoring_rule(tournament_config):
    stored = tournament_config.get("scoring_rule", {})
    if not isinstance(stored, Mapping):
        raise ValidationError({"scoringRule": "Ожидается объект правил подсчёта."})
    return {
        "order": stored.get(
            "order", ["solved_desc", "penalty_asc", "last_accepted_asc"]
        ),
        "wrongAttemptPenaltySec": stored.get("wrong_attempt_penalty_sec", 60),
        "penalizedVerdicts": stored.get(
            "penalized_verdicts", ["WA", "TL", "ML", "RE"]
        ),
        "finalTiePolicy": stored.get("final_tie_policy", "rematch"),
    }


def _match_detail_queryset(request):
    queryset = (
        Match.objects.filter(kind=Match.Kind.PLAYED)
        .select_related("tournament", "current_run", "winner__user")
    )
    if request.user.role != User.Roles.ADMIN:
        queryset = queryset.filter(
            slots__resolution=MatchSlot.Resolution.PLAYER,
            slots__participant__user=request.user,
            slots__participant__status=TournamentParticipant.Status.ACTIVE,
        )
    return queryset


def _match_response(match, *, actor):
    try:
        payload = match_view_payload(match, actor=actor, now=timezone.now())
    except MatchProjectionError as error:
        raise MatchRequestError(str(error), code=error.code) from error
    response = Response(payload, status=status.HTTP_200_OK)
    response["Cache-Control"] = "no-store"
    return response


@method_decorator(csrf_protect, name="dispatch")
class MatchDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [MatchReadPermission()]
        return [IsApplicationAdmin()]

    def get(self, request, match_id):
        match = get_object_or_404(_match_detail_queryset(request), pk=match_id)
        return _match_response(match, actor=request.user)

    def patch(self, request, match_id):
        serializer = StrictMatchConfigRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _require_match_idempotency_key(request)
        match = get_object_or_404(
            Match.objects.select_related("tournament"), pk=match_id
        )
        if match.kind != Match.Kind.PLAYED:
            raise MatchRequestError(
                "Автоматический проход нельзя настраивать как матч.",
                code="match_not_playable",
            )

        config = serializer.validated_data
        tournament_config = match.tournament.default_match_config
        scoring_rule = _runtime_scoring_rule(tournament_config)
        try:
            configure_match_run(
                match.pk,
                problem_ids=config["problem_ids"],
                allowed_duration_ms=config["match_duration_sec"] * 1000,
                start_mode=config["start_mode"],
                scoring_rule=scoring_rule,
                catalog=DjangoProblemCatalog(),
            )
        except MatchRuntimeError as error:
            raise MatchRequestError(
                str(error),
                code=error.code,
                status_code=error.status_code,
            ) from error

        updated = get_object_or_404(
            Match.objects.select_related("tournament", "current_run", "winner__user"),
            pk=match_id,
        )
        return _match_response(updated, actor=request.user)


@method_decorator(csrf_protect, name="dispatch")
class StartMatchView(APIView):
    permission_classes = [IsApplicationAdmin]

    def post(self, request, match_id):
        serializer = StrictEmptyObjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _require_match_idempotency_key(request)
        match = get_object_or_404(
            Match.objects.select_related("current_run"), pk=match_id
        )
        if match.kind != Match.Kind.PLAYED or match.current_run_id is None:
            raise MatchRequestError(
                "Сначала настройте запускаемый матч.",
                code="match_run_not_configured",
            )
        try:
            start_match_run(match.current_run_id, now=timezone.now())
        except MatchRuntimeError as error:
            raise MatchRequestError(
                str(error),
                code=error.code,
                status_code=error.status_code,
            ) from error

        updated = get_object_or_404(
            Match.objects.select_related("tournament", "current_run", "winner__user"),
            pk=match_id,
        )
        return _match_response(updated, actor=request.user)


class GenerateBracketRequestSerializer(serializers.Serializer):
    seeding_mode = serializers.ChoiceField(choices=("manual",))

    def to_internal_value(self, data):
        if not isinstance(data, Mapping) or set(data) != {"seeding_mode"}:
            raise ValidationError(
                {"seeding_mode": "Укажите единственное поле seedingMode=manual."}
            )
        return super().to_internal_value(data)


class StrictPositionField(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            raise ValidationError("Позиция должна быть целым числом.")
        return super().to_internal_value(data)


class FirstRoundPairingRequestSerializer(serializers.Serializer):
    position = StrictPositionField(min_value=0)
    left_user_id = serializers.UUIDField(allow_null=True)
    right_user_id = serializers.UUIDField(allow_null=True)

    def to_internal_value(self, data):
        if not isinstance(data, Mapping) or set(data) != {
            "position",
            "left_user_id",
            "right_user_id",
        }:
            raise ValidationError(
                {
                    "non_field_errors": (
                        "Каждая пара должна содержать position, leftUserId и rightUserId."
                    )
                }
            )
        return super().to_internal_value(data)


class SetFirstRoundPairingsRequestSerializer(serializers.Serializer):
    pairings = FirstRoundPairingRequestSerializer(many=True, allow_empty=False)
    reason = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)

    def to_internal_value(self, data):
        if not isinstance(data, Mapping) or set(data) != {"pairings", "reason"}:
            raise ValidationError(
                {"non_field_errors": "Ожидаются только поля pairings и reason."}
            )
        return super().to_internal_value(data)

    def validate_pairings(self, value):
        positions = [pairing["position"] for pairing in value]
        if positions != list(range(len(positions))):
            raise ValidationError(
                "Позиции первого раунда должны идти подряд от нуля."
            )
        return value


class ResetBracketRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)

    def to_internal_value(self, data):
        if not isinstance(data, Mapping) or set(data) != {"reason"}:
            raise ValidationError(
                {"non_field_errors": "Ожидается только поле reason."}
            )
        return super().to_internal_value(data)


class StrictAdminActionRequestSerializer(serializers.Serializer):
    """Reject unknown fields so clients cannot supply trusted actor/state data."""

    def to_internal_value(self, data):
        if not isinstance(data, Mapping) or set(data) != set(self.fields):
            allowed = ", ".join(sorted(self.fields)) or "no fields"
            raise ValidationError({"non_field_errors": f"Expected exactly: {allowed}."})
        return super().to_internal_value(data)


class PauseMatchRequestSerializer(StrictAdminActionRequestSerializer):
    reason = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)


class ResumeMatchRequestSerializer(StrictAdminActionRequestSerializer):
    pass


class ExtendMatchRequestSerializer(StrictAdminActionRequestSerializer):
    seconds = StrictPositionField(min_value=1, max_value=600)
    reason = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)


class TechnicalResultRequestSerializer(StrictAdminActionRequestSerializer):
    winner_user_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)


class ReasonOnlyMatchRequestSerializer(StrictAdminActionRequestSerializer):
    reason = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)


class ReplaceParticipantRequestSerializer(StrictAdminActionRequestSerializer):
    old_user_id = serializers.UUIDField()
    new_user_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)


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


def current_bracket_payload(tournament_id):
    tournament = Tournament.objects.get(pk=tournament_id)
    matches = list(bracket_match_queryset().filter(tournament_id=tournament.pk))
    return bracket_payload(tournament, matches)


def _idempotency_key(request):
    key = request.headers.get("Idempotency-Key")
    if key is None:
        raise ValidationError({"Idempotency-Key": "This header is required."})
    return key


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


@method_decorator(csrf_protect, name="dispatch")
class SetFirstRoundPairingsView(APIView):
    permission_classes = [IsApplicationAdmin]

    def put(self, request, tournament_id):
        serializer = SetFirstRoundPairingsRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        command = serializer.validated_data

        def perform():
            active_entries = {
                user_id: entry_id
                for entry_id, user_id in TournamentParticipant.objects.filter(
                    tournament_id=tournament_id,
                    status=TournamentParticipant.Status.ACTIVE,
                ).values_list("id", "user_id")
            }
            requested_user_ids = {
                user_id
                for pairing in command["pairings"]
                for user_id in (pairing["left_user_id"], pairing["right_user_id"])
                if user_id is not None
            }
            if not requested_user_ids <= set(active_entries):
                raise BracketInputError(
                    "Ручные пары могут содержать только активных участников турнира."
                )
            entry_pairings = [
                (
                    active_entries.get(pairing["left_user_id"]),
                    active_entries.get(pairing["right_user_id"]),
                )
                for pairing in command["pairings"]
            ]
            set_first_round_pairings(tournament_id, entry_pairings)
            return current_bracket_payload(tournament_id)

        try:
            payload = execute_bracket_command(
                tournament_id=tournament_id,
                actor_id=request.user.pk,
                action="bracket.pairings",
                idempotency_key=_idempotency_key(request),
                reason=command["reason"],
                arguments={
                    "pairings": [
                        {
                            "position": pairing["position"],
                            "leftUserId": pairing["left_user_id"],
                            "rightUserId": pairing["right_user_id"],
                        }
                        for pairing in command["pairings"]
                    ]
                },
                perform=perform,
            )
        except BracketCommandInputError as error:
            raise ValidationError({"Idempotency-Key": str(error)}) from error
        except BracketCommandIdempotencyConflict as error:
            raise BracketRequestError(error) from error
        except Tournament.DoesNotExist as error:
            raise NotFound("Турнир не найден.") from error
        except BracketInputError as error:
            raise ValidationError({"pairings": str(error)}) from error
        except (RosterMutationError, BracketPersistenceError) as error:
            raise BracketRequestError(error) from error

        response = Response(payload, status=status.HTTP_200_OK)
        response["Cache-Control"] = "no-store"
        return response


@method_decorator(csrf_protect, name="dispatch")
class ResetBracketView(APIView):
    permission_classes = [IsApplicationAdmin]

    def post(self, request, tournament_id):
        serializer = ResetBracketRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        command = serializer.validated_data

        def perform():
            reset_bracket(tournament_id)
            return current_bracket_payload(tournament_id)

        try:
            payload = execute_bracket_command(
                tournament_id=tournament_id,
                actor_id=request.user.pk,
                action="bracket.reset",
                idempotency_key=_idempotency_key(request),
                reason=command["reason"],
                arguments={},
                perform=perform,
            )
        except BracketCommandInputError as error:
            raise ValidationError({"Idempotency-Key": str(error)}) from error
        except BracketCommandIdempotencyConflict as error:
            raise BracketRequestError(error) from error
        except Tournament.DoesNotExist as error:
            raise NotFound("Турнир не найден.") from error
        except (RosterMutationError, BracketPersistenceError) as error:
            raise BracketRequestError(error) from error

        response = Response(payload, status=status.HTTP_200_OK)
        response["Cache-Control"] = "no-store"
        return response


class MatchAdminActionRequestError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "admin_command_conflict"

    def __init__(self, error):
        self.status_code = getattr(error, "status_code", self.status_code)
        self.default_code = getattr(error, "code", self.default_code)
        super().__init__(detail=str(error), code=self.default_code)


class MatchAdminActionView(APIView):
    permission_classes = [IsApplicationAdmin]
    action = None
    serializer_class = None

    def command_arguments(self, values):
        if self.action is AdminAction.EXTEND:
            return {"seconds": values["seconds"], "reason": values["reason"]}
        if self.action is AdminAction.TECHNICAL_RESULT:
            return {
                "winner_user_id": values["winner_user_id"],
                "reason": values["reason"],
            }
        if self.action is AdminAction.REPLACE_PARTICIPANT:
            return {
                "old_user_id": values["old_user_id"],
                "replacement_user_id": values["new_user_id"],
                "reason": values["reason"],
            }
        if self.action in (AdminAction.PAUSE, AdminAction.REMATCH):
            return {"reason": values["reason"]}
        return {}

    def post(self, request, match_id):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = execute_match_admin_command(
                actor_user_id=request.user.pk,
                match_id=match_id,
                command_id=_idempotency_key(request),
                action=self.action,
                **self.command_arguments(serializer.validated_data),
            )
        except AdminCommandPersistenceError as error:
            raise MatchAdminActionRequestError(error) from error
        response = Response(payload, status=status.HTTP_200_OK)
        response["Cache-Control"] = "no-store"
        return response


@method_decorator(csrf_protect, name="dispatch")
class PauseMatchView(MatchAdminActionView):
    action = AdminAction.PAUSE
    serializer_class = PauseMatchRequestSerializer


@method_decorator(csrf_protect, name="dispatch")
class ResumeMatchView(MatchAdminActionView):
    action = AdminAction.RESUME
    serializer_class = ResumeMatchRequestSerializer


@method_decorator(csrf_protect, name="dispatch")
class ExtendMatchView(MatchAdminActionView):
    action = AdminAction.EXTEND
    serializer_class = ExtendMatchRequestSerializer


@method_decorator(csrf_protect, name="dispatch")
class TechnicalResultView(MatchAdminActionView):
    action = AdminAction.TECHNICAL_RESULT
    serializer_class = TechnicalResultRequestSerializer


@method_decorator(csrf_protect, name="dispatch")
class RematchView(MatchAdminActionView):
    action = AdminAction.REMATCH
    serializer_class = ReasonOnlyMatchRequestSerializer


@method_decorator(csrf_protect, name="dispatch")
class ReplaceParticipantView(MatchAdminActionView):
    action = AdminAction.REPLACE_PARTICIPANT
    serializer_class = ReplaceParticipantRequestSerializer


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
