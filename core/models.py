from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model — extend this as your project requires."""

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email or self.username
