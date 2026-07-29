from celery import Celery

from app.core.config.settings import settings

celery_app = Celery(
    "student_management_backend",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.timezone = "Asia/Kolkata"
