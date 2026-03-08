"""
Development settings.
"""

from .base import *  # noqa: F401, F403

# django_browser_reload is in INSTALLED_APPS via base.py — insert middleware early so
# it runs before anything that might short-circuit the request (e.g. WhiteNoise).
MIDDLEWARE.insert(1, "django_browser_reload.middleware.BrowserReloadMiddleware")  # noqa: F405

# Use plain static files storage in dev — no manifest required
STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

# In-memory channel layer in dev (set in base.py)
# EMAIL_BACKEND already set to console in base.py

# Run Celery tasks synchronously (inline) when a broker is unavailable.
# This ensures jobs are processed immediately in development without needing
# a running Redis + Celery worker.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
