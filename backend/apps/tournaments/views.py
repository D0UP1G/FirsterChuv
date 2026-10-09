"""Tournament and roster endpoints with explicit global-role boundaries."""

from uuid import UUID

from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response

from backend.apps.accounts.models import User
from backend.apps.accounts.permissions import IsApplicationAdmin
from backend.apps.tournaments.models import Tournament, TournamentParticipant
from backend.apps.tournaments.serializers import (
    AdminUserOptionSerializer,
    AssignParticipantSerializer,
    ParticipantSeedSerializer,
    TournamentParticipantSerializer,
    TournamentSerializer,
)
from backend.apps.tournaments.services import (
    RosterMutationError,
    assign_participant,
    remove_participant,
    set_participant_seed,
)


class TournamentPagination(LimitOffsetPagination):
    default_limit = 25
    max_limit = 100


class IsActiveAdminOrParticipant(BasePermission):
    message = "Требуется активная учётная запись participant или admin."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role in (User.Roles.ADMIN, User.Roles.PARTICIPANT)
        )

    def has_object_permission(self, request, view, tournament):
        user = request.user
        if user.role == User.Roles.ADMIN:
            return True
        if request.method not in SAFE_METHODS:
            return False
        return TournamentParticipant.objects.filter(
            tournament=tournament,
            user=user,
            status=TournamentParticipant.Status.ACTIVE,
        ).exists()


class RosterMutationResponse(APIException):
    status_code = 409
    default_code = "roster_conflict"

    def __init__(self, error):
        self.status_code = error.status_code
        self.default_code = error.code
        super().__init__(detail=str(error), code=error.code)


def raise_roster_error(error: RosterMutationError):
    if error.status_code == 404:
        raise NotFound(str(error))
    if error.status_code == 400:
        raise ValidationError({"userId": str(error)}, code=error.code)
    raise RosterMutationResponse(error)


class AdminUserPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 100


class AdminUserDirectoryView(generics.ListAPIView):
    """Minimal, paginated lookup for assigning existing participant accounts."""

    serializer_class = AdminUserOptionSerializer
    permission_classes = [IsApplicationAdmin]
    pagination_class = AdminUserPagination

    def get_queryset(self):
        search = self.request.query_params.get("q", "").strip()
        if len(search) > 80:
            raise ValidationError({"q": "Запрос поиска не должен превышать 80 символов."})
        requested_role = self.request.query_params.get("role")
        if requested_role not in (None, User.Roles.PARTICIPANT):
            raise ValidationError({"role": "Доступен только каталог participant."})
        queryset = User.objects.filter(
            is_active=True,
            role=User.Roles.PARTICIPANT,
        ).order_by("display_name", "id")
        if search:
            queryset = queryset.filter(display_name__icontains=search)
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


@method_decorator(csrf_protect, name="dispatch")
class TournamentViewSet(viewsets.ModelViewSet):
    """Admins manage tournaments; participants read only their active entries."""

    queryset = Tournament.objects.select_related("created_by")
    serializer_class = TournamentSerializer
    permission_classes = [IsActiveAdminOrParticipant]
    pagination_class = TournamentPagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsActiveAdminOrParticipant()]
        return [IsApplicationAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role == User.Roles.ADMIN:
            return queryset
        return queryset.filter(
            participants__user=user,
            participants__status=TournamentParticipant.Status.ACTIVE,
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        with transaction.atomic():
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
            if (
                instance.status == Tournament.Status.DRAFT
                and instance.roster_frozen_at is None
            ):
                instance.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)

            instance.status = Tournament.Status.ARCHIVED
            instance.save(update_fields=("status", "updated_at"))
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="participants")
    def participants(self, request, pk=None):
        tournament = self.get_object()
        if request.method == "GET":
            entries = TournamentParticipant.objects.select_related("user").filter(
                tournament=tournament,
            )
            if request.user.role != User.Roles.ADMIN:
                entries = entries.filter(status=TournamentParticipant.Status.ACTIVE)
            page = self.paginate_queryset(entries)
            serializer = TournamentParticipantSerializer(
                page if page is not None else entries,
                many=True,
            )
            if page is not None:
                return self.get_paginated_response(serializer.data)
            return Response(serializer.data)

        serializer = AssignParticipantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entry, created = assign_participant(
                tournament.id,
                serializer.validated_data["user_id"],
                seed=serializer.validated_data.get("seed"),
            )
        except RosterMutationError as error:
            raise_roster_error(error)
        return Response(
            TournamentParticipantSerializer(entry).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"participants/(?P<user_id>[^/.]+)",
        url_name="participant",
    )
    def participant(self, request, pk=None, user_id=None):
        tournament = self.get_object()
        try:
            participant_id = UUID(user_id)
        except (TypeError, ValueError) as exc:
            raise NotFound("Участник не найден.") from exc

        if request.method == "PATCH":
            serializer = ParticipantSeedSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                entry = set_participant_seed(
                    tournament.id,
                    participant_id,
                    serializer.validated_data["seed"],
                )
            except RosterMutationError as error:
                raise_roster_error(error)
            return Response(TournamentParticipantSerializer(entry).data)

        try:
            remove_participant(tournament.id, participant_id)
        except RosterMutationError as error:
            raise_roster_error(error)
        return Response(status=status.HTTP_204_NO_CONTENT)
