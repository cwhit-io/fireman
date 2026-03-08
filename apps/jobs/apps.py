from django.apps import AppConfig


class JobsConfig(AppConfig):
    name = "apps.jobs"
    verbose_name = "Print Jobs"

    def ready(self):
        from .signals import cleanup  # noqa: F401
