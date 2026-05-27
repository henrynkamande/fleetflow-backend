from django.contrib.auth.backends import ModelBackend

from oauth.models import User


class EmailBackend(ModelBackend):
    """Authenticate with email + password (USERNAME_FIELD is email)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (username or kwargs.get(User.USERNAME_FIELD) or '').strip().lower()
        if not email or password is None:
            return None
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
