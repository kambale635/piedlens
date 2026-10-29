from shared_kernel.domain_exceptions import DomainException


class InvalidPaymentTransition(DomainException):
    """Raised when a payment attempt transition violates INV-PAY-06."""


class PaymentAmountMismatch(DomainException):
    """Raised when a provider event differs from the immutable payable (INV-PAY-01/07)."""
