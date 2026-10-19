from shared_kernel.application_exceptions import (
    ResourceNotFoundException,
    ValidationException,
)


class TrialUnavailableException(ValidationException):
    error_code = "TRIAL_UNAVAILABLE"


class TrialCardRequiredException(ValidationException):
    error_code = "TRIAL_CARD_REQUIRED"


class CouponNotFoundException(ResourceNotFoundException):
    error_code = "COUPON_NOT_FOUND"


class CouponNotValidException(ValidationException):
    error_code = "COUPON_NOT_VALID"


class CouponAlreadyUsedException(ValidationException):
    error_code = "COUPON_ALREADY_USED"


class ReferralNotValidException(ValidationException):
    error_code = "REFERRAL_NOT_VALID"


class ReferralAlreadyRedeemedException(ValidationException):
    error_code = "REFERRAL_ALREADY_REDEEMED"


class ReferralLimitReachedException(ValidationException):
    error_code = "REFERRAL_LIMIT_REACHED"