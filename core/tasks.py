import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def example_task(name: str) -> str:
    """Example Celery task."""
    return f"Hello, {name}!"
