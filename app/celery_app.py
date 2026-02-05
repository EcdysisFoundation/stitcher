from celery import Celery
import os

celery = Celery(
    "stitcher",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6360/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6360/0"),
)

celery.autodiscover_tasks(["app"])
