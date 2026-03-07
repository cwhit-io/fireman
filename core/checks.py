"""
Django system checks for environment variable validation.

These run automatically on every `manage.py` invocation and server start,
failing fast with a clear message if required variables are missing or
still set to placeholder values.
"""

import os

from django.core.checks import Error, Warning, register

REQUIRED_VARS = [
    "SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "DJANGO_SETTINGS_MODULE",
]

INSECURE_PLACEHOLDERS = {
    "SECRET_KEY": {"your-secret-key-here", "changeme", "insecure"},
}


@register()
def check_required_env_vars(app_configs, **kwargs):
    errors = []

    for var in REQUIRED_VARS:
        if not os.environ.get(var):
            errors.append(
                Error(
                    f"Environment variable {var!r} is not set.",
                    hint=f"Add {var} to your .env file. See .env.example for reference.",
                    id=f"core.E00{REQUIRED_VARS.index(var) + 1}",
                )
            )

    return errors


@register()
def check_secret_key_placeholder(app_configs, **kwargs):
    warnings = []

    secret_key = os.environ.get("SECRET_KEY", "")
    placeholders = INSECURE_PLACEHOLDERS.get("SECRET_KEY", set())

    if any(p in secret_key for p in placeholders):
        warnings.append(
            Warning(
                "SECRET_KEY appears to be a placeholder value.",
                hint='Generate a real key with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"',
                id="core.W001",
            )
        )

    return warnings
