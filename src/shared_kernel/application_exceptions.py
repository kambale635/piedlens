class ApplicationException(Exception):
    """Base exception for application-layer failures mapped outside domain rules."""


class ResourceNotFoundException(ApplicationException):
    """Raised when a requested resource does not exist in the caller's scope."""


class ValidationException(ApplicationException):
    """Raised when an application command contains an invalid value."""