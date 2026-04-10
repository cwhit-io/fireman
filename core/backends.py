from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Allow authentication with either a username or an email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()

        if username is None:
            return None

        # Try exact username match first
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Fall back to case-insensitive email lookup
            try:
                user = User.objects.get(email__iexact=username)
            except User.DoesNotExist:
                # Run the default password hasher to mitigate timing attacks
                User().set_password(password)
                return None
            except User.MultipleObjectsReturned:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
