from shared_kernel.domain_exceptions import DomainException


class InvalidRuleScopeException(DomainException):
    """Reject a malformed or out-of-tenant rule scope (INV-RE-01)."""

    status_code = 400
    error_code = "INVALID_RULE_SCOPE"