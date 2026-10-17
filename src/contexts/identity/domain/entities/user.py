from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ..value_objects.identity_values import EmailAddress, PhoneNumber, UserStatus


@dataclass(frozen=True)
class User:
    id: UUID
    phone_number: PhoneNumber
    email: EmailAddress | None
    password_hash: str
    status: UserStatus
    created_at: datetime

    @classmethod
    def register(
        cls,
        user_id: UUID,
        phone_number: PhoneNumber,
        email: EmailAddress | None,
        password_hash: str,
        created_at: datetime,
    ) -> "User":
        """Create a User with a password hash only (INV-ID-04)."""
        return cls(user_id, phone_number, email, password_hash, UserStatus.ACTIVE, created_at)