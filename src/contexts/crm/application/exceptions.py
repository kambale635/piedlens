from shared_kernel.application_exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

from ..domain.exceptions import ContactAlreadyMergedException


class InvalidContactIdentityException(ValidationException):
    """Rejects missing platform identity fields before CRM persistence."""


class UnknownSegmentFieldException(ValidationException):
    """Reject invalid CRM segment fields before persistence."""


class UnsupportedSegmentOperatorException(ValidationException):
    """Reject unsupported CRM segment operators before persistence."""


class ContactNotFoundException(ResourceNotFoundException):
    """Reject a merge when a contact is absent or outside the merchant scope."""


class ContactsMustBeDistinctException(ValidationException):
    """Reject an invalid merge command that names the same Contact twice."""