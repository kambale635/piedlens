import base64
import re
from collections.abc import Mapping


REQUIRED_PRODUCTION_VARIABLES = (
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "POSTGRES_PASSWORD",
    "REDIS_URL",
    "PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION",
    "PLATFORM_MESSAGE_ENCRYPTION_ACTIVE_VERSION",
    "CRM_MESSAGE_ENCRYPTION_ACTIVE_VERSION",
    "BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION",
    "WHATSAPP_WEBHOOK_SECRET",
    "INSTAGRAM_WEBHOOK_SECRET",
    "FACEBOOK_WEBHOOK_SECRET",
    "BACKUP_EXPORT_SIGNING_SECRET",
    "BACKUP_DELETE_CONFIRMATION_SECRET",
    "HEALTH_METRICS_TOKEN",
)

S3_PRODUCTION_VARIABLES = (
    "BACKUP_S3_BUCKET",
    "BACKUP_S3_ACCESS_KEY_ID",
    "BACKUP_S3_SECRET_ACCESS_KEY",
)


def environment_security_settings(environ: Mapping[str, str]) -> dict[str, object]:
    """Build secure transport/cookie defaults, forcing them on in production."""
    production = environ.get("DJANGO_ENV") == "production"
    hsts_default = "31536000" if production else "0"
    hsts_seconds = int(environ.get("DJANGO_SECURE_HSTS_SECONDS", hsts_default))
    if production and hsts_seconds < 1:
        raise RuntimeError("DJANGO_SECURE_HSTS_SECONDS must be positive in production.")
    return {
        "SESSION_COOKIE_SECURE": production or environ.get("DJANGO_SECURE_COOKIES") == "1",
        "CSRF_COOKIE_SECURE": production or environ.get("DJANGO_SECURE_COOKIES") == "1",
        "SECURE_SSL_REDIRECT": production or environ.get("DJANGO_SECURE_SSL_REDIRECT") == "1",
        "SECURE_HSTS_SECONDS": hsts_seconds,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": production
        or environ.get("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS") == "1",
        "SECURE_HSTS_PRELOAD": environ.get("DJANGO_SECURE_HSTS_PRELOAD") == "1",
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "SECURE_REFERRER_POLICY": "strict-origin-when-cross-origin",
        "X_FRAME_OPTIONS": "DENY",
    }


def validate_production_configuration(environ: Mapping[str, str]) -> None:
    """Reject production configuration with missing secrets or debug enabled."""
    if environ.get("DJANGO_ENV") != "production":
        return

    required_variables = list(REQUIRED_PRODUCTION_VARIABLES)
    if environ.get("BACKUP_OBJECT_STORAGE_BACKEND", "postgres") == "s3":
        required_variables.extend(S3_PRODUCTION_VARIABLES)
    active_version = environ.get("PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION", "").strip()
    if active_version and re.fullmatch(r"v[1-9][0-9]*", active_version) is None:
        raise RuntimeError("PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION must be vN.")
    active_key_name = None
    if active_version:
        active_key_name = f"PLATFORM_TOKEN_ENCRYPTION_KEY_{active_version.upper()}"
        encoded_key = environ.get(active_key_name, "")
        if encoded_key.strip():
            try:
                decoded_key = base64.b64decode(
                    encoded_key.encode("ascii"), altchars=b"-_", validate=True
                )
            except (ValueError, UnicodeEncodeError) as error:
                raise RuntimeError(f"{active_key_name} must be URL-safe base64.") from error
            if len(decoded_key) != 32:
                raise RuntimeError(f"{active_key_name} must decode to 32 bytes.")
    backup_version = environ.get("BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION", "").strip()
    if backup_version and re.fullmatch(r"v[1-9][0-9]*", backup_version) is None:
        raise RuntimeError("BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION must be vN.")
    backup_key_name = None
    if backup_version:
        backup_key_name = f"BACKUP_DATA_ENCRYPTION_KEY_{backup_version.upper()}"
        encoded_key = environ.get(backup_key_name, "")
        if encoded_key.strip():
            try:
                decoded_key = base64.b64decode(
                    encoded_key.encode("ascii"), altchars=b"-_", validate=True
                )
            except (ValueError, UnicodeEncodeError) as error:
                raise RuntimeError(f"{backup_key_name} must be URL-safe base64.") from error
            if len(decoded_key) != 32:
                raise RuntimeError(f"{backup_key_name} must decode to 32 bytes.")
    message_version = environ.get("PLATFORM_MESSAGE_ENCRYPTION_ACTIVE_VERSION", "").strip()
    if message_version and re.fullmatch(r"v[1-9][0-9]*", message_version) is None:
        raise RuntimeError("PLATFORM_MESSAGE_ENCRYPTION_ACTIVE_VERSION must be vN.")
    message_key_name = None
    if message_version:
        message_key_name = f"PLATFORM_MESSAGE_ENCRYPTION_KEY_{message_version.upper()}"
        encoded_key = environ.get(message_key_name, "")
        if encoded_key.strip():
            try:
                decoded_key = base64.b64decode(
                    encoded_key.encode("ascii"), altchars=b"-_", validate=True
                )
            except (ValueError, UnicodeEncodeError) as error:
                raise RuntimeError(f"{message_key_name} must be URL-safe base64.") from error
            if len(decoded_key) != 32:
                raise RuntimeError(f"{message_key_name} must decode to 32 bytes.")
    crm_version = environ.get("CRM_MESSAGE_ENCRYPTION_ACTIVE_VERSION", "").strip()
    if crm_version and re.fullmatch(r"v[1-9][0-9]*", crm_version) is None:
        raise RuntimeError("CRM_MESSAGE_ENCRYPTION_ACTIVE_VERSION must be vN.")
    crm_key_name = None
    if crm_version:
        crm_key_name = f"CRM_MESSAGE_ENCRYPTION_KEY_{crm_version.upper()}"
        encoded_key = environ.get(crm_key_name, "")
        if encoded_key.strip():
            try:
                decoded_key = base64.b64decode(
                    encoded_key.encode("ascii"), altchars=b"-_", validate=True
                )
            except (ValueError, UnicodeEncodeError) as error:
                raise RuntimeError(f"{crm_key_name} must be URL-safe base64.") from error
            if len(decoded_key) != 32:
                raise RuntimeError(f"{crm_key_name} must decode to 32 bytes.")
    missing_variables = [name for name in required_variables if not environ.get(name, "").strip()]
    if active_key_name and not environ.get(active_key_name, "").strip():
        missing_variables.append(active_key_name)
    if backup_key_name and not environ.get(backup_key_name, "").strip():
        missing_variables.append(backup_key_name)
    if message_key_name and not environ.get(message_key_name, "").strip():
        missing_variables.append(message_key_name)
    if crm_key_name and not environ.get(crm_key_name, "").strip():
        missing_variables.append(crm_key_name)
    if missing_variables:
        missing = ", ".join(missing_variables)
        raise RuntimeError(f"Missing required production environment variables: {missing}.")
    if environ.get("DJANGO_DEBUG", "0") == "1":
        raise RuntimeError("DJANGO_DEBUG must be disabled in production.")