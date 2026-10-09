"""Global application-role permissions; Django staff flags are not roles."""

from rest_framework.permissions import BasePermission

from backend.apps.accounts.models import User


class HasGlobalRole(BasePermission):
    role = None
    message = "Недостаточно прав для этого действия."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role == self.role
        )

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsApplicationAdmin(HasGlobalRole):
    role = User.Roles.ADMIN


class IsParticipant(HasGlobalRole):
    role = User.Roles.PARTICIPANT
