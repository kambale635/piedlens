from ...domain.value_objects.identity_values import PhoneNumber, UserStatus
from ..exceptions.identity_exceptions import AccountDisabled, InvalidCredentials
from ..ports.identity_ports import ILoginBackoff, IPasswordHasher, ITokenService, IUserRepository


class AuthenticateUserUseCase:
    """Authenticate without disclosing whether a phone number exists (INV-ID-05)."""

    def __init__(
        self,
        users: IUserRepository,
        password_hasher: IPasswordHasher,
        token_service: ITokenService,
        backoff: ILoginBackoff,
    ) -> None:
        self.users = users
        self.password_hasher = password_hasher
        self.token_service = token_service
        self.backoff = backoff

    def execute(self, phone_number: str, password: str, source_ip: str = "") -> dict:
        """Return the same credential error for missing users and wrong passwords (INV-ID-05)."""
        normalized_phone = PhoneNumber(phone_number).value
        attempt_key = f"{source_ip}:{normalized_phone}"
        if self.backoff.is_blocked(attempt_key):
            raise InvalidCredentials()
        user = self.users.find_by_phone(normalized_phone)
        if user is None or not self.password_hasher.verify(password, user.password_hash):
            self.backoff.record_failure(attempt_key)
            raise InvalidCredentials()
        self.backoff.clear(attempt_key)
        if user.status is UserStatus.DISABLED:
            raise AccountDisabled()
        return self.token_service.issue_tokens(user.id)