from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from core.admin_mixins import ImportExportAdminMixin

from .models import User


@admin.register(User)
class UserAdmin(ImportExportAdminMixin, BaseUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "can_use_mail_merge")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Permissions (Fireman)", {"fields": ("can_use_mail_merge",)}),
    )
    import_label = "Users"
    export_filename = "users.json"
    export_key = "users"
    export_note = (
        "Passwords are not included. "
        "Imported users are created with no usable password and must have "
        "their password set via the admin before they can log in."
    )
    import_note = (
        "Passwords are not exported or imported. "
        "New users will be created with no usable password — "
        "set a password for each via the admin change form before they log in."
    )

    def obj_to_dict(self, obj):
        return {
            "username": obj.username,
            "email": obj.email,
            "first_name": obj.first_name,
            "last_name": obj.last_name,
            "is_staff": obj.is_staff,
            "is_active": obj.is_active,
            "is_superuser": obj.is_superuser,
            "can_use_mail_merge": obj.can_use_mail_merge,
        }

    def dict_to_obj(self, d, overwrite):
        username = (d.get("username") or "").strip()
        if not username:
            return ("error", "Skipped entry with missing username.")
        fields = {
            "email": d.get("email", ""),
            "first_name": d.get("first_name", ""),
            "last_name": d.get("last_name", ""),
            "is_staff": bool(d.get("is_staff", False)),
            "is_active": bool(d.get("is_active", True)),
            "is_superuser": bool(d.get("is_superuser", False)),
            "can_use_mail_merge": bool(d.get("can_use_mail_merge", False)),
        }
        existing = User.objects.filter(username=username).first()
        if existing:
            if overwrite:
                for k, v in fields.items():
                    setattr(existing, k, v)
                existing.save()
                return ("updated", None)
            return ("skipped", None)
        user = User(username=username, **fields)
        user.set_unusable_password()
        user.save()
        return ("created", None)
