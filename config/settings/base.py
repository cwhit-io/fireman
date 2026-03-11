"""
Base Django settings shared by all environments.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["10.10.96.138", "localhost", "127.0.0.1ember.bhm.li"]),
    INTERNAL_IPS=(list, ["127.0.0.1"]),
    # SECRET_KEY has no default — raises ImproperlyConfigured if not set
    DATABASE_URL=(str, f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
    REDIS_URL=(str, "redis://localhost:6379/0"),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
INTERNAL_IPS = env("INTERNAL_IPS")

# Application definition
INSTALLED_APPS = [
    "django_daisy",  # must be before django.contrib.admin
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",  # required by django-daisy
    # Third-party
    "channels",
    "ninja",
    "django_browser_reload",
    # Local
    "core",
    # Apps
    "apps.jobs",
    "apps.impose",
    "apps.cutter",
    "apps.routing",
    "apps.rules",
]

AUTH_USER_MODEL = "core.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Wagtail middleware removed
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
DATABASES = {
    "default": env.db("DATABASE_URL"),
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Fiery print queue username shown on the Fiery job list
FIERY_PRINT_USER = env("FIERY_PRINT_USER", default="Ember")

# ── Preflight constants ──────────────────────────────────────────────────────
# Required bleed (0.125" = 9pt)
BLEED_PT = env.float("BLEED_PT", default=9.0)
# Expected Canva crop-mark zone per side
CANVA_MARGIN_PT = env.float("CANVA_MARGIN_PT", default=17.0)
# Tolerance around Canva detection (±5pt)
CANVA_WIGGLE_PT = env.float("CANVA_WIGGLE_PT", default=5.0)
# Rounding tolerance for exact size match
SIZE_TOLERANCE_PT = env.float("SIZE_TOLERANCE_PT", default=1.0)
# Aspect-ratio mismatch threshold (%)
AR_TOLERANCE_PCT = env.float("AR_TOLERANCE_PCT", default=2.0)
# Below this DPI: will pixelate (critical)
DPI_MINIMUM = env.int("DPI_MINIMUM", default=150)
# Below this DPI: marginal quality warning
DPI_WARN = env.int("DPI_WARN", default=300)
# Minimum distance from trim edge to live content (pt)
SAFE_ZONE_PT = env.float("SAFE_ZONE_PT", default=9.0)
# RGB colorspace triggers warning when False
ALLOW_RGB = env.bool("ALLOW_RGB", default=False)
# Spot/Pantone colors allowed without warning
ALLOW_SPOT = env.bool("ALLOW_SPOT", default=True)

# ── File upload limits ───────────────────────────────────────────────────────
# Maximum PDF upload size in bytes (default: 50 MB)
MAX_PDF_UPLOAD_BYTES = env.int("MAX_PDF_UPLOAD_BYTES", default=50 * 1024 * 1024)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Django Channels
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Celery
REDIS_URL = env("REDIS_URL")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
