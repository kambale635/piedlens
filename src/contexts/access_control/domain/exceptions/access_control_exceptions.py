from shared_kernel.domain_exceptions import DomainException


class InsufficientPrivilegeToGrant(DomainException):
    """Raised when requested permissions exceed the actor's scope grants (INV-AC-02)."""

    status_code = 403
    error_code = "INSUFFICIENT_PRIVILEGE_TO_GRANT"