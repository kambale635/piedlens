from shared_kernel.application_exceptions import ResourceNotFoundException, ValidationException


class InvalidRuleWeightException(ValidationException):
    """Reject a rule weight outside the catalogued 0-100 range."""

    error_code = "INVALID_RULE_WEIGHT"


class EmptyRulePatternException(ValidationException):
    """Reject a rule without a configured pattern (INV-RE-04)."""

    error_code = "EMPTY_PATTERN"


class RuleSetNotFoundException(ResourceNotFoundException):
    """Report a missing merchant-scoped RuleSet or rule without leaking other scopes."""