from shared_kernel.application_exceptions import (
    PlanUpgradeRequiredException,
    ResourceNotFoundException,
    ValidationException,
)

from ...domain.exceptions.crm_exceptions import ContactAlreadyMergedException


class InvalidContactIdentityException(ValidationException):
    """Rejects missing platform identity fields before CRM persistence."""


class UnknownSegmentFieldException(ValidationException):
    """Reject invalid CRM segment fields before persistence."""


class UnsupportedSegmentOperatorException(ValidationException):
    """Reject unsupported CRM segment operators before persistence."""


class InvalidSegmentValueException(ValidationException):
    """Reject segment values incompatible with their field and operator."""


class SegmentCurrencyRequiredException(ValidationException):
    """Reject a total-spent segment rule that does not declare its currency (INV-CRM-08)."""

    error_code = "CURRENCY_REQUIRED"


class InvalidSegmentPaginationException(ValidationException):
    """Reject non-positive page values before evaluating a segment."""


class SegmentLimitReachedException(PlanUpgradeRequiredException):
    """Reject segment creation after the configured plan quota is reached (INV-PLAN-01)."""

    def __init__(self, entitlement_key: str = "max_segments"):
        super().__init__(entitlement_key)


class SegmentNotFoundException(ResourceNotFoundException):
    """Reject membership requests for a segment that does not exist."""


class BulkMessageChannelException(ValidationException):
    """Reject a campaign channel not supported by the CRM contract."""


class BulkMessageCampaignNotFoundException(ResourceNotFoundException):
    """Reject processing requests for campaigns absent from CRM persistence."""


class ContactNotFoundException(ResourceNotFoundException):
    """Reject a merge when a contact is absent or outside the merchant scope."""


class ContactsMustBeDistinctException(ValidationException):
    """Reject an invalid merge command that names the same Contact twice."""