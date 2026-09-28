from shared_kernel.domain_exceptions import DomainException


class InvalidRelationshipAnomalyPolicyException(DomainException):
    """Reject invalid anomaly policy values that would break INV-CRM-05."""


class ContactAlreadyMergedException(DomainException):
    """Reject a second merge transition of a Contact tombstone (INV-CRM-07)."""