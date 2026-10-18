from shared_kernel.application_exceptions import ResourceNotFoundException, ValidationException


class BackupConsentRequiredException(ValidationException):
    """Reject customer-data backup without explicit merchant consent (INV-BK-03)."""

    status_code = 422
    error_code = "BACKUP_CONSENT_REQUIRED"


class InvalidConfirmationTokenException(ValidationException):
    """Reject deletion without a valid second confirmation token (INV-BK-04)."""

    status_code = 403
    error_code = "INVALID_CONFIRMATION_TOKEN"


class InvalidReauthenticationException(ValidationException):
    """Reject deletion requests when the authenticated user's password is invalid (INV-BK-05)."""

    status_code = 401
    error_code = "INVALID_CREDENTIALS"


class BackupSnapshotNotFoundException(ResourceNotFoundException):
    """Report no successful snapshot or export in the requesting merchant scope."""


class InvalidExportSignatureException(ValidationException):
    """Reject an invalid or expired bearer URL signature for a backup object."""

    status_code = 403
    error_code = "INVALID_EXPORT_SIGNATURE"