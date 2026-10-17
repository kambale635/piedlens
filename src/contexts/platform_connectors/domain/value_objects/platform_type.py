from enum import StrEnum


class PlatformType(StrEnum):
    """Supported connector types available to the first-party mock gateway."""

    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"