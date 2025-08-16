import os
from celery import Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pennywise_api.settings")
app = Celery("pennywise_api")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
celery_app = app
