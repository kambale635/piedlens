from ...domain.value_objects.identity_values import PhoneNumber, UserStatus
from ..exceptions.identity_exceptions import AccountDisabled, InvalidCredentials
from ..ports.identity_ports import IPasswordHasher, ITokenService, IUserRepository


class AuthenticateUserUseCase:
    """Authenticate without disclosing whether a phone number exists (INV-ID-05)."""

    def __init__(self, users: IUserRepository, password_hasher: IPasswordHasher,
                 token_service: ITokenService) -> None:
        self.users = users
        self.password_hasher = password_hasher
        self.token_service = token_service

    def execute(self, phone_number: str, password: str) -> dict:
        """Return the same credential error for missing users and wrong passwords (INV-ID-05)."""
        user = self.users.find_by_phone(PhoneNumber(phone_number).value)
        if user is None or not self.password_hasher.verify(password, user.password_hash):
            raise InvalidCredentials()
        if user.status is UserStatus.DISABLED:
            raise AccountDisabled()
        return self.token_service.issue_tokens(user.id)