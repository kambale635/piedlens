import re
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class PlatformType:
    """Extensible channel code; support is configuration/registry-driven (INV-PC-06)."""

    value: str
    _CODE: ClassVar[re.Pattern] = re.compile(r"^[a-z][a-z0-9_]{1,63}$")

    def __post_init__(self) -> None:
        if not self._CODE.fullmatch(self.value):
            raise ValueError("Channel code must be a lowercase identifier.")

    def __str__(self) -> str:
        return self.value


PlatformType.WHATSAPP = PlatformType("whatsapp")
PlatformType.INSTAGRAM = PlatformType("instagram")
PlatformType.FACEBOOK = PlatformType("facebook")