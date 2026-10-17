from dataclasses import dataclass

from shared_kernel.domain_exceptions import InvalidValueObjectException


@dataclass(frozen=True)
class EncryptedToken:
    """Opaque encrypted credential; plaintext is confined to infrastructure (INV-PC-01)."""

    value: str

    def __post_init__(self) -> None:
        """Reject an absent encrypted value so persistence never implies a credential."""
        if not isinstance(self.value, str) or not self.value.strip():
            raise InvalidValueObjectException("Encrypted token must not be empty.")