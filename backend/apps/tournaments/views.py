"""Tournament and roster endpoints with explicit global-role boundaries."""

from uuid import UUID

from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import (
    AllowAny,
    BasePermission,
    IsAuthenticated,
    SAFE_METHODS,
)
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from backend.apps.accounts.models import User
from backend.apps.accounts.permissions import IsApplicationAdmin, IsParticipant
from backend.apps.tournaments.models import Invite, Tournament, TournamentParticipant
from backend.apps.tournaments.serializers import (
    AdminUserOptionSerializer,
    AssignParticipantSerializer,
    InviteCreateSerializer,
    InviteMetadataSerializer,
    ParticipantSeedSerializer,
    TournamentParticipantSerializer,
    TournamentSerializer,
)
from backend.apps.tournaments.services import (
    InviteMutationError,
    RosterMutationError,
    accept_invite,
    assign_participant,
    create_invite,
    invite_for_token,
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


class InvitePagination(LimitOffsetPagination):
    default_limit = 25
    max_limit = 100


class InviteMutationResponse(APIException):
    status_code = 409
    default_code = "invite_conflict"

    def __init__(self, error):
        self.status_code = error.status_code
        self.default_code = error.code
        super().__init__(detail=str(error), code=error.code)


def raise_invite_error(error: InviteMutationError):
    if error.status_code == 404:
        raise NotFound(str(error))
    raise InviteMutationResponse(error)


class PrivateInviteAPIView(APIView):
    """Apply private/no-referrer response headers to every invite response."""

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response


@method_decorator(csrf_protect, name="dispatch")
class TournamentInvitesView(PrivateInviteAPIView):
    permission_classes = [IsApplicationAdmin]
    pagination_class = InvitePagination

    def get_tournament(self):
        try:
            return Tournament.objects.get(pk=self.kwargs["tournament_id"])
        except Tournament.DoesNotExist as exc:
            raise NotFound("Турнир не найден.") from exc

    def get(self, request, tournament_id):
        tournament = self.get_tournament()
        invites = Invite.objects.filter(tournament=tournament)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(invites, request, view=self)
        return paginator.get_paginated_response(
            InviteMetadataSerializer(page, many=True).data
        )

    def post(self, request, tournament_id):
        tournament = self.get_tournament()
        serializer = InviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invite, token = create_invite(
                tournament,
                request.user,
                expires_at=serializer.validated_data.get("expires_at"),
                max_uses=serializer.validated_data.get("max_uses"),
            )
        except RosterMutationError as error:
            raise_roster_error(error)
        metadata = InviteMetadataSerializer(invite).data
        return Response(
            {
                "invite": metadata,
                "token": token,
                "url": f"/invites/{token}",
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name="dispatch")
class TournamentInviteRevokeView(PrivateInviteAPIView):
    permission_classes = [IsApplicationAdmin]

    def delete(self, request, tournament_id, invite_id):
        invite = Invite.objects.filter(
            pk=invite_id,
            tournament_id=tournament_id,
        ).first()
        if invite is None:
            raise NotFound("Приглашение не найдено.")
        if invite.revoked_at is None:
            Invite.objects.filter(pk=invite.pk, revoked_at__isnull=True).update(
                revoked_at=timezone.now()
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitePreviewView(PrivateInviteAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "invite_preview"

    def get(self, request, token):
        try:
            invite = invite_for_token(token)
        except InviteMutationError as error:
            raise_invite_error(error)
        return Response(
            {
                "tournament": {
                    "id": invite.tournament_id,
                    "title": invite.tournament.title,
                },
                "valid": True,
                "expires_at": invite.expires_at,
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class InviteAcceptView(PrivateInviteAPIView):
    permission_classes = [IsAuthenticated, IsParticipant]

    def post(self, request, token):
        if request.data not in ({}, None):
            raise ValidationError({"detail": "Тело запроса должно быть пустым."})
        try:
            invite, _created = accept_invite(token, request.user)
        except InviteMutationError as error:
            raise_invite_error(error)
        except RosterMutationError as error:
            raise_roster_error(error)
        return Response(
            {
                "tournament_id": invite.tournament_id,
                "user_id": request.user.id,
                "joined": True,
            },
            status=status.HTTP_200_OK,
        )


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
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                self.perform_update(serializer)
        except RosterMutationError as error:
            raise_roster_error(error)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        with transaction.atomic():
            now = timezone.now()
            if (
                instance.status == Tournament.Status.DRAFT
                and instance.roster_frozen_at is None
                and Tournament.objects.filter(
                    pk=instance.pk,
                    updated_at=instance.updated_at,
                    status=Tournament.Status.DRAFT,
                    roster_frozen_at__isnull=True,
                ).update(status=Tournament.Status.ARCHIVED, updated_at=now)
            ):
                Tournament.objects.filter(pk=instance.pk).delete()
                return Response(status=status.HTTP_204_NO_CONTENT)

            current = Tournament.objects.filter(pk=instance.pk).first()
            if current is None or current.status == Tournament.Status.ARCHIVED:
                return Response(status=status.HTTP_204_NO_CONTENT)
            archived = Tournament.objects.filter(
                pk=current.pk,
                updated_at=current.updated_at,
            ).update(status=Tournament.Status.ARCHIVED, updated_at=now)
            if archived == 0:
                raise_roster_error(
                    RosterMutationError("Турнир успел измениться; повторите удаление.")
                )
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
