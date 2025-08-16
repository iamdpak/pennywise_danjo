import os
from pathlib import Path
from urllib.parse import urlparse
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")
INSTALLED_APPS = [
    "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes",
    "django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
    "rest_framework","drf_spectacular","apps.receipts",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware","django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware","django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware","django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "pennywise_api.urls"
TEMPLATES = [{
  "BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[],"APP_DIRS":True,
  "OPTIONS":{"context_processors":[
    "django.template.context_processors.debug","django.template.context_processors.request",
    "django.contrib.auth.context_processors.auth","django.contrib.messages.context_processors.messages"]}
}]
WSGI_APPLICATION = "pennywise_api.wsgi:application"
DATABASE_URL = os.getenv("DATABASE_URL", "postgres://postgres:password@localhost:5432/pennywise")
p = urlparse(DATABASE_URL)
DATABASES = {"default": {"ENGINE":"django.db.backends.postgresql","NAME":p.path.lstrip("/"),
    "USER":p.username,"PASSWORD":p.password,"HOST":p.hostname,"PORT":p.port or 5432}}
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
REST_FRAMEWORK = {"DEFAULT_SCHEMA_CLASS":"drf_spectacular.openapi.AutoSchema"}
SPECTACULAR_SETTINGS = {"TITLE":"PennyWise Receipt AI API","VERSION":"1.0.0","SERVE_INCLUDE_SCHEMA":False}
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
LLM_PROVIDER_URL = os.getenv("LLM_PROVIDER_URL", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2-vision")
