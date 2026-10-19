class ApplicationException(Exception):
    """Base exception for application-layer failures mapped outside domain rules."""


class ResourceNotFoundException(ApplicationException):
    """Raised when a requested resource does not exist in the caller's scope."""


class ValidationException(ApplicationException):
    """Raised when an application command contains an invalid value."""


class PlanUpgradeRequiredException(ApplicationException):
    """Report the exact entitlement missing from the merchant's active plan."""

    status_code = 402
    error_code = "PLAN_UPGRADE_REQUIRED"

    def __init__(self, entitlement_key: str) -> None:
        self.entitlement_key = entitlement_key
        super().__init__(entitlement_key)


class OutboundQuotaExceededException(ApplicationException):
    """Signal that the configured monthly API message cap would be exceeded."""

    status_code = 422
    error_code = "OUTBOUND_CAP_REACHED"