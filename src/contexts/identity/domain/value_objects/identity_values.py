import re
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from shared_kernel.domain_exceptions import InvalidValueObjectException


@dataclass(frozen=True)
class PhoneNumber:
    value: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"\+[1-9][0-9]{0,14}", self.value):
            raise InvalidValueObjectException("Phone number must use E.164 format.")


@dataclass(frozen=True)
class EmailAddress:
    value: str

    def __post_init__(self) -> None:
        if self.value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", self.value):
            raise InvalidValueObjectException("Email address is invalid.")


@dataclass(frozen=True)
class CountryCode:
    value: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Z]{2}", self.value):
            raise InvalidValueObjectException("Country code must be ISO 3166-1 alpha-2.")


@dataclass(frozen=True)
class LanguageCode:
    value: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z]{2}", self.value):
            raise InvalidValueObjectException("Language code must be ISO 639-1.")


@dataclass(frozen=True)
class CurrencyCode:
    value: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Z]{3}", self.value):
            raise InvalidValueObjectException("Currency code must be ISO 4217.")


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


@dataclass(frozen=True)
class UserId:
    value: UUID


@dataclass(frozen=True)
class MerchantId:
    value: UUID