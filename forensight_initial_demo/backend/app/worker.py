"""Celery placeholder for the later production stack.

The initial demo executes analysis synchronously so no Redis/Celery setup is
required tomorrow. This file shows exactly where GPU jobs will move later.
"""
from celery import Celery
from .config import settings

celery_app = Celery("forensight", broker=settings.redis_url, backend=settings.redis_url)
