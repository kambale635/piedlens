import base64
import re
from collections.abc import Mapping


REQUIRED_PRODUCTION_VARIABLES = (
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "POSTGRES_PASSWORD",
    "REDIS_URL",
    "PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION",
    "WHATSAPP_WEBHOOK_SECRET",
    "INSTAGRAM_WEBHOOK_SECRET",
    "FACEBOOK_WEBHOOK_SECRET",
    "BACKUP_EXPORT_SIGNING_SECRET",
    "BACKUP_DELETE_CONFIRMATION_SECRET",
)

S3_PRODUCTION_VARIABLES = (
    "BACKUP_S3_BUCKET",
    "BACKUP_S3_ACCESS_KEY_ID",
    "BACKUP_S3_SECRET_ACCESS_KEY",
)


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
    missing_variables = [name for name in required_variables if not environ.get(name, "").strip()]
    if active_key_name and not environ.get(active_key_name, "").strip():
        missing_variables.append(active_key_name)
    if missing_variables:
        missing = ", ".join(missing_variables)
        raise RuntimeError(f"Missing required production environment variables: {missing}.")
    if environ.get("DJANGO_DEBUG", "0") == "1":
        raise RuntimeError("DJANGO_DEBUG must be disabled in production.")