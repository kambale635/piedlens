from uuid import uuid4

from shared_kernel.domain_exceptions import InvalidValueObjectException
from ...domain.entities.user import User
from ...domain.events.identity_events import UserRegistered
from ...domain.value_objects.identity_values import EmailAddress, PhoneNumber
from ..exceptions.identity_exceptions import InvalidPhoneFormat, PhoneAlreadyRegistered, WeakPassword
from ..ports.identity_ports import (
    IIdentityClock,
    IIdentityOutbox,
    IIdentityUnitOfWork,
    IPasswordHasher,
    IUserRepository,
)


class RegisterUserUseCase:
    """Register a User and append UserRegistered atomically (INV-ID-02/04)."""

    def __init__(self, users: IUserRepository, password_hasher: IPasswordHasher,
                 unit_of_work: IIdentityUnitOfWork, outbox: IIdentityOutbox,
                 clock: IIdentityClock) -> None:
        self.users = users
        self.password_hasher = password_hasher
        self.unit_of_work = unit_of_work
        self.outbox = outbox
        self.clock = clock

    def execute(self, phone_number: str, password: str, email: str | None = None) -> dict:
        """Persist a unique phone and a hash, never the supplied password (INV-ID-02/04)."""
        try:
            phone = PhoneNumber(phone_number)
        except InvalidValueObjectException as error:
            raise InvalidPhoneFormat() from error
        if not self.password_hasher.validate(password):
            raise WeakPassword()
        if self.users.find_by_phone(phone.value) is not None:
            raise PhoneAlreadyRegistered()
        email_value = EmailAddress(email) if email else None
        user = User.register(
            uuid4(), phone, email_value, self.password_hasher.hash(password), self.clock.now_utc()
        )
        with self.unit_of_work:
            self.users.save(user)
            self.outbox.add(UserRegistered(user.id))
        return {"userId": user.id}