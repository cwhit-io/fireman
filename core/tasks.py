from celery import shared_task


@shared_task
def example_task(name: str) -> str:
    """Example Celery task."""
    return f"Hello, {name}!"
