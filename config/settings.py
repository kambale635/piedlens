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
    "contexts.rules_engine.apps.RulesEngineConfig",
    "contexts.identity.apps.IdentityConfig",
    "contexts.access_control.apps.AccessControlConfig",
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
    "middleware.request_id_middleware.RequestIdMiddleware",
    "middleware.exception_handling_middleware.ExceptionHandlingMiddleware",
    "middleware.authentication_middleware.AuthenticationMiddleware",
    "middleware.tenant_isolation_middleware.TenantIsolationMiddleware",
    "middleware.permission_middleware.PermissionMiddleware",
    "middleware.rate_limit_middleware.RateLimitMiddleware",
    "middleware.audit_logging_middleware.AuditLoggingMiddleware",
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
IDENTITY_ACCESS_TOKEN_TTL_SECONDS = int(os.environ.get("IDENTITY_ACCESS_TOKEN_TTL_SECONDS", "900"))
IDENTITY_REFRESH_TOKEN_TTL_SECONDS = int(
    os.environ.get("IDENTITY_REFRESH_TOKEN_TTL_SECONDS", "2592000")
)
ACCESS_CONTROL_PERMISSION_CACHE_TTL_SECONDS = int(
    os.environ.get("ACCESS_CONTROL_PERMISSION_CACHE_TTL_SECONDS", "15")
)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "TIMEOUT": ACCESS_CONTROL_PERMISSION_CACHE_TTL_SECONDS,
    }
}
PIEDLENS_AUTHENTICATOR = (
    "contexts.identity.infrastructure.adapters.http_authentication.authenticate_request"
)
PIEDLENS_PERMISSION_CHECKER = (
    "contexts.access_control.infrastructure.adapters.django_permission_checker."
    "DjangoAccessControlPermissionChecker"
)
CRM_SEGMENT_CACHE_TTL_SECONDS = int(
    os.environ.get("CRM_SEGMENT_CACHE_TTL_SECONDS", "300")
)
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