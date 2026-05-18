from celery import Celery

from app.config import get_settings


settings = get_settings()

celery = Celery(
    "nexusintel",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    timezone="UTC",
)
