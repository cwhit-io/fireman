from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model — extend this as your project requires."""

    can_use_mail_merge = models.BooleanField(
        default=False,
        help_text="Allow this user to access the Mail Merge feature.",
    )

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email or self.username
