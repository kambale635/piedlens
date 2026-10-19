from shared_kernel.application_exceptions import (
    PlanUpgradeRequiredException,
    ResourceNotFoundException,
    ValidationException,
)
class PlanConnectionLimitReachedException(PlanUpgradeRequiredException):
    """Reject another active connection when the merchant plan limit is reached (INV-ID-01)."""

    def __init__(self, entitlement_key: str = "max_connections"):
        super().__init__(entitlement_key)


class InvalidWebhookSignatureException(ValidationException):
    """Reject unsigned or tampered webhook bodies before any parsing (INV-PC-02)."""

    status_code = 401
    error_code = "INVALID_WEBHOOK_SIGNATURE"


class InvalidOAuthCodeException(ValidationException):
    """Reject an invalid OAuth exchange result without exposing provider details."""

    error_code = "INVALID_OAUTH_CODE"


class PlatformConnectionNotFoundException(ResourceNotFoundException):
    """Report a missing or inactive connection without revealing another merchant's data."""