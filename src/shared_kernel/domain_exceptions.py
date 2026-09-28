class DomainException(Exception):
    """Base exception for business-rule violations raised by pure domain code."""


class InvalidValueObjectException(DomainException):
    """Raised when a shared value object cannot represent the supplied value."""


class CurrencyMismatchException(DomainException):
    """Raised when Money arithmetic mixes currencies, protecting INV-OD-05/INV-TR-05."""