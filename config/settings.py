import os
import secrets
from pathlib import Path

from .security_settings import environment_security_settings, validate_production_configuration
from .observability import initialize_sentry_if_configured


BASE_DIR = Path(__file__).resolve().parent.parent
validate_production_configuration(os.environ)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or secrets.token_urlsafe(50)
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
globals().update(environment_security_settings(os.environ))

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "piedlens_platform.event_bus.apps.EventBusConfig",
    "contexts.rules_engine.apps.RulesEngineConfig",
    "contexts.identity.apps.IdentityConfig",
    "contexts.billing.apps.BillingConfig",
    "contexts.access_control.apps.AccessControlConfig",
    "contexts.platform_connectors.apps.PlatformConnectorsConfig",
    "contexts.backup.apps.BackupConfig",
    "contexts.order_detection.apps.OrderDetectionConfig",
    "contexts.crm.apps.CRMConfig",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "middleware.cors_middleware.CorsMiddleware",
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
    "middleware.request_size_limit_middleware.RequestSizeLimitMiddleware",
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
HEALTH_OUTBOX_LAG_ALERT_SECONDS = int(
    os.environ.get("HEALTH_OUTBOX_LAG_ALERT_SECONDS", "300")
)
HEALTH_DLQ_SIZE_ALERT_THRESHOLD = int(os.environ.get("HEALTH_DLQ_SIZE_ALERT_THRESHOLD", "1"))
HEALTH_METRICS_TOKEN = os.environ.get("HEALTH_METRICS_TOKEN", "")
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
IDENTITY_LOGIN_BACKOFF_BASE_SECONDS = int(
    os.environ.get("IDENTITY_LOGIN_BACKOFF_BASE_SECONDS", "2")
)
IDENTITY_LOGIN_BACKOFF_MAX_SECONDS = int(
    os.environ.get("IDENTITY_LOGIN_BACKOFF_MAX_SECONDS", "900")
)
IDENTITY_LOGIN_BACKOFF_WINDOW_SECONDS = int(
    os.environ.get("IDENTITY_LOGIN_BACKOFF_WINDOW_SECONDS", "3600")
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
PIEDLENS_AUDIT_SINK = "piedlens_platform.event_bus.audit_log.DjangoAuditLogSink"
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
BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION = os.environ.get(
    "BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION", "v1"
)
BACKUP_DATA_ENCRYPTION_KEYS = {
    name.removeprefix("BACKUP_DATA_ENCRYPTION_KEY_").lower(): value
    for name, value in os.environ.items()
    if name.startswith("BACKUP_DATA_ENCRYPTION_KEY_") and value
}
PLATFORM_MESSAGE_ENCRYPTION_ACTIVE_VERSION = os.environ.get(
    "PLATFORM_MESSAGE_ENCRYPTION_ACTIVE_VERSION", "v1"
)
PLATFORM_MESSAGE_ENCRYPTION_KEYS = {
    name.removeprefix("PLATFORM_MESSAGE_ENCRYPTION_KEY_").lower(): value
    for name, value in os.environ.items()
    if name.startswith("PLATFORM_MESSAGE_ENCRYPTION_KEY_") and value
}
CRM_MESSAGE_ENCRYPTION_ACTIVE_VERSION = os.environ.get(
    "CRM_MESSAGE_ENCRYPTION_ACTIVE_VERSION", "v1"
)
CRM_MESSAGE_ENCRYPTION_KEYS = {
    name.removeprefix("CRM_MESSAGE_ENCRYPTION_KEY_").lower(): value
    for name, value in os.environ.items()
    if name.startswith("CRM_MESSAGE_ENCRYPTION_KEY_") and value
}
PLATFORM_WEBHOOK_SECRETS = {
    "whatsapp": os.environ.get("WHATSAPP_WEBHOOK_SECRET", ""),
    "instagram": os.environ.get("INSTAGRAM_WEBHOOK_SECRET", ""),
    "facebook": os.environ.get("FACEBOOK_WEBHOOK_SECRET", ""),
}
PLATFORM_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = int(
    os.environ.get("PLATFORM_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS", "300")
)
if PLATFORM_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS < 1:
    raise RuntimeError("PLATFORM_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS must be positive.")
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
DJANGO_MAX_REQUEST_BODY_BYTES = int(os.environ.get("DJANGO_MAX_REQUEST_BODY_BYTES", "10485760"))
if DJANGO_MAX_REQUEST_BODY_BYTES < 1:
    raise RuntimeError("DJANGO_MAX_REQUEST_BODY_BYTES must be positive.")
DATA_UPLOAD_MAX_MEMORY_SIZE = DJANGO_MAX_REQUEST_BODY_BYTES
FILE_UPLOAD_MAX_MEMORY_SIZE = min(DJANGO_MAX_REQUEST_BODY_BYTES, 2621440)
CORS_ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
)
if "*" in CORS_ALLOWED_ORIGINS or "null" in CORS_ALLOWED_ORIGINS:
    raise RuntimeError("CORS_ALLOWED_ORIGINS must list exact non-null origins.")
CORS_ALLOWED_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
CORS_ALLOWED_HEADERS = ("authorization", "content-type", "x-correlation-id", "x-merchant-id")
PIEDLENS_ALERT_HOOK = os.environ.get("PIEDLENS_ALERT_HOOK", "")
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = os.environ.get(
    "SENTRY_ENVIRONMENT", os.environ.get("DJANGO_ENV", "development")
)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "piedlens_platform.logging.JsonLogFormatter"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}

initialize_sentry_if_configured()