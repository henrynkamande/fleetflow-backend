from rest_framework.permissions import BasePermission

from oauth.models import User


class IsPlatformAdmin(BasePermission):
    """Only users with PLATFORM_ADMIN role may access platform API routes."""

    message = 'Platform administrator access required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, 'role', None) == User.Role.PLATFORM_ADMIN
        )
