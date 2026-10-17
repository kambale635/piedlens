from shared_kernel.application_exceptions import ApplicationException


class IdentityApplicationException(ApplicationException):
    status_code = 400
    error_code = "IDENTITY_ERROR"


class PhoneAlreadyRegistered(IdentityApplicationException):
    status_code = 409
    error_code = "PHONE_ALREADY_REGISTERED"


class WeakPassword(IdentityApplicationException):
    status_code = 400
    error_code = "WEAK_PASSWORD"


class InvalidPhoneFormat(IdentityApplicationException):
    error_code = "INVALID_PHONE_FORMAT"


class InvalidCredentials(IdentityApplicationException):
    status_code = 401
    error_code = "INVALID_CREDENTIALS"


class AccountDisabled(IdentityApplicationException):
    status_code = 403
    error_code = "ACCOUNT_DISABLED"


class InvalidRefreshToken(IdentityApplicationException):
    status_code = 401
    error_code = "INVALID_REFRESH_TOKEN"


class MerchantNotFound(IdentityApplicationException):
    status_code = 404
    error_code = "MERCHANT_NOT_FOUND"


class InvalidMerchantData(IdentityApplicationException):
    status_code = 400
    error_code = "VALIDATION_ERROR"