import os


def initialize_sentry_if_configured() -> None:
    """Initialize Sentry only when SENTRY_DSN is supplied by the runtime environment."""
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError as error:
        raise RuntimeError("SENTRY_DSN is configured but sentry-sdk is not installed.") from error
    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", os.environ.get("DJANGO_ENV", "development")),
    )
