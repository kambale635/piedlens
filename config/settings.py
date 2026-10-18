import os
import secrets
from pathlib import Path

from .security_settings import validate_production_configuration


BASE_DIR = Path(__file__).resolve().parent.parent
validate_production_configuration(os.environ)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or secrets.token_urlsafe(50)
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "piedlens_platform.event_bus.apps.EventBusConfig",
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
        "OPTIONS": {
            "sslmode": os.environ.get("POSTGRES_SSLMODE", "prefer"),
            **(
                {"sslrootcert": os.environ["POSTGRES_SSLROOTCERT"]}
                if os.environ.get("POSTGRES_SSLROOTCERT")
                else {}
            ),
        },
    }
}

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
REDIS_TLS_CA_CERTS = os.environ.get("REDIS_TLS_CA_CERTS") or None
REDIS_CLIENT_OPTIONS = {
    "ssl_ca_certs": REDIS_TLS_CA_CERTS,
    "ssl_cert_reqs": "required" if REDIS_TLS_CA_CERTS else None,
}
OUTBOX_RELAY_BATCH_SIZE = int(os.environ.get("OUTBOX_RELAY_BATCH_SIZE", "100"))
OUTBOX_RELAY_POLL_INTERVAL_SECONDS = float(
    os.environ.get("OUTBOX_RELAY_POLL_INTERVAL_SECONDS", "1")
)
OUTBOX_RELAY_BACKOFF_BASE_SECONDS = float(
    os.environ.get("OUTBOX_RELAY_BACKOFF_BASE_SECONDS", "1")
)
OUTBOX_RELAY_BACKOFF_MAX_SECONDS = float(
    os.environ.get("OUTBOX_RELAY_BACKOFF_MAX_SECONDS", "300")
)
STREAM_CLAIM_IDLE_MS = int(os.environ.get("STREAM_CLAIM_IDLE_MS", "60000"))
STREAM_MAX_DELIVERIES = int(os.environ.get("STREAM_MAX_DELIVERIES", "5"))
CONSUMER_CONTEXT = os.environ.get("CONSUMER_CONTEXT", "")
ORDER_DETECTION_CONFIDENCE_THRESHOLD = int(
    os.environ.get("ORDER_DETECTION_CONFIDENCE_THRESHOLD", "70")
)
ORDER_DETECTION_CORRELATION_WINDOW_DAYS = int(
    os.environ.get("ORDER_DETECTION_CORRELATION_WINDOW_DAYS", "3")
)
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
        "OPTIONS": {"ssl_ca_certs": REDIS_TLS_CA_CERTS} if REDIS_TLS_CA_CERTS else {},
        "TIMEOUT": ACCESS_CONTROL_PERMISSION_CACHE_TTL_SECONDS,
    }
}
PLATFORM_ADAPTERS = {
    "whatsapp": os.environ.get("WHATSAPP_ADAPTER", "mock"),
    "instagram": os.environ.get("INSTAGRAM_ADAPTER", "mock"),
    "facebook": os.environ.get("FACEBOOK_ADAPTER", "mock"),
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
ORDER_REMINDER_DELAYS_SECONDS = {
    "payment_pending": int(os.environ.get("ORDER_PAYMENT_REMINDER_DELAY_SECONDS", "86400")),
    "delivery_pending": int(os.environ.get("ORDER_DELIVERY_REMINDER_DELAY_SECONDS", "86400")),
}
PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION = os.environ.get(
    "PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION", "v1"
)
PLATFORM_TOKEN_ENCRYPTION_KEYS = {
    name.removeprefix("PLATFORM_TOKEN_ENCRYPTION_KEY_").lower(): value
    for name, value in os.environ.items()
    if name.startswith("PLATFORM_TOKEN_ENCRYPTION_KEY_") and value
}
if os.environ.get("PLATFORM_TOKEN_ENCRYPTION_KEY"):
    PLATFORM_TOKEN_ENCRYPTION_KEYS.setdefault(
        "legacy", os.environ["PLATFORM_TOKEN_ENCRYPTION_KEY"]
    )
PLATFORM_WEBHOOK_SECRETS = {
    "whatsapp": os.environ.get("WHATSAPP_WEBHOOK_SECRET", ""),
    "instagram": os.environ.get("INSTAGRAM_WEBHOOK_SECRET", ""),
    "facebook": os.environ.get("FACEBOOK_WEBHOOK_SECRET", ""),
}
BACKUP_EXPORT_SIGNING_SECRET = os.environ.get("BACKUP_EXPORT_SIGNING_SECRET", "")
BACKUP_EXPORT_BASE_URL = os.environ.get(
    "BACKUP_EXPORT_BASE_URL", "http://localhost:8000/api/v1/backups/objects"
)
BACKUP_EXPORT_TTL_MINUTES = int(os.environ.get("BACKUP_EXPORT_TTL_MINUTES", "60"))
BACKUP_DELETE_CONFIRMATION_SECRET = os.environ.get("BACKUP_DELETE_CONFIRMATION_SECRET", "")
BACKUP_OBJECT_STORAGE_BACKEND = os.environ.get("BACKUP_OBJECT_STORAGE_BACKEND", "postgres")
BACKUP_S3_BUCKET = os.environ.get("BACKUP_S3_BUCKET", "")
BACKUP_S3_REGION = os.environ.get("BACKUP_S3_REGION", "us-east-1")
BACKUP_S3_ENDPOINT_URL = os.environ.get("BACKUP_S3_ENDPOINT_URL", "")
BACKUP_S3_ACCESS_KEY_ID = os.environ.get("BACKUP_S3_ACCESS_KEY_ID", "")
BACKUP_S3_SECRET_ACCESS_KEY = os.environ.get("BACKUP_S3_SECRET_ACCESS_KEY", "")
BACKUP_S3_USE_TLS = os.environ.get("BACKUP_S3_USE_TLS", "1") == "1"
BACKUP_S3_VERIFY_TLS = os.environ.get("BACKUP_S3_VERIFY_TLS", "1") == "1"
BACKUP_S3_DELETE_BATCH_SIZE = int(os.environ.get("BACKUP_S3_DELETE_BATCH_SIZE", "100"))
BACKUP_S3_DELETE_BACKOFF_BASE_SECONDS = float(
    os.environ.get("BACKUP_S3_DELETE_BACKOFF_BASE_SECONDS", "2")
)
BACKUP_S3_DELETE_BACKOFF_MAX_SECONDS = float(
    os.environ.get("BACKUP_S3_DELETE_BACKOFF_MAX_SECONDS", "300")
)
if os.environ.get("DJANGO_SECURE_COOKIES", "0") == "1":
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "0") == "1"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"