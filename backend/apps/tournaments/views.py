"""Admin-only tournament management endpoints."""

from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status, viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from backend.apps.accounts.permissions import IsApplicationAdmin
from backend.apps.tournaments.models import Tournament
from backend.apps.tournaments.serializers import TournamentSerializer


class TournamentPagination(LimitOffsetPagination):
    default_limit = 25
    max_limit = 100


@method_decorator(csrf_protect, name="dispatch")
class TournamentViewSet(viewsets.ModelViewSet):
    """A global application admin owns tournament CRUD in the MVP."""

    queryset = Tournament.objects.select_related("created_by")
    serializer_class = TournamentSerializer
    permission_classes = [IsApplicationAdmin]
    pagination_class = TournamentPagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

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
