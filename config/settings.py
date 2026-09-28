import os
import secrets
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or secrets.token_urlsafe(50)
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "shared_kernel.rules_engine.apps.RulesEngineConfig",
    "shared_kernel.identity.apps.IdentityConfig",
    "shared_kernel.access_control.apps.AccessControlConfig",
    "contexts.platform_connectors.apps.PlatformConnectorsConfig",
    "contexts.backup.apps.BackupConfig",
    "contexts.order_detection.apps.OrderDetectionConfig",
    "contexts.crm.apps.CRMConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "piedlens"),
        "USER": os.environ.get("POSTGRES_USER", "piedlens"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CRM_ANOMALY_MIN_PURCHASES = int(os.environ.get("CRM_ANOMALY_MIN_PURCHASES", "3"))
CRM_ANOMALY_MULTIPLIER = os.environ.get("CRM_ANOMALY_MULTIPLIER", "2.0")
CRM_ANOMALY_MIN_INACTIVITY_DAYS = int(
    os.environ.get("CRM_ANOMALY_MIN_INACTIVITY_DAYS", "7")
)
CRM_RELATIONSHIP_ANOMALY_BY_MERCHANT = {}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"