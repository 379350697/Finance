from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "finance_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)
