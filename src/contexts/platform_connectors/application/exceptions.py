from shared_kernel.application_exceptions import ResourceNotFoundException, ValidationException
from shared_kernel.domain_exceptions import DomainException


class PlanConnectionLimitReachedException(DomainException):
    """Reject another active connection when the merchant plan limit is reached (INV-ID-01)."""

    status_code = 422
    error_code = "PLAN_CONNECTION_LIMIT_REACHED"


class InvalidWebhookSignatureException(ValidationException):
    """Reject unsigned or tampered webhook bodies before any parsing (INV-PC-02)."""

    status_code = 401
    error_code = "INVALID_WEBHOOK_SIGNATURE"


class InvalidOAuthCodeException(ValidationException):
    """Reject an invalid OAuth exchange result without exposing provider details."""

    error_code = "INVALID_OAUTH_CODE"


class PlatformConnectionNotFoundException(ResourceNotFoundException):
    """Report a missing or inactive connection without revealing another merchant's data."""