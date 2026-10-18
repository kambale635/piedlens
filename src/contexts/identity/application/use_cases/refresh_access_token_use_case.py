from ...domain.value_objects.identity_values import UserStatus
from ..exceptions.identity_exceptions import InvalidRefreshToken
from ..ports.identity_ports import ITokenService, IUserRepository


class RefreshAccessTokenUseCase:
    """Exchange a valid refresh token for a new access token."""

    def __init__(self, token_service: ITokenService, users: IUserRepository) -> None:
        self.token_service = token_service
        self.users = users

    def execute(self, refresh_token: str) -> dict:
        """Reject malformed, expired, or non-refresh tokens with one public error."""
        try:
            issued = self.token_service.refresh_access_token(refresh_token)
            user = self.users.find_by_id(issued["userId"])
            if user is None or user.status is not UserStatus.ACTIVE:
                self.token_service.revoke_refresh_token(issued["refreshToken"])
                raise InvalidRefreshToken()
            return {
                "accessToken": issued["accessToken"],
                "refreshToken": issued["refreshToken"],
                "expiresAt": issued["expiresAt"],
            }
        except InvalidRefreshToken:
            raise
        except Exception as error:
            raise InvalidRefreshToken() from error