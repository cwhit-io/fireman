from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "can_use_mail_merge")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Permissions (Fireman)", {"fields": ("can_use_mail_merge",)}),
    )
