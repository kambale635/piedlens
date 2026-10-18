from ..ports.identity_ports import ITokenService


class LogoutUserUseCase:
    """Revoke one refresh-token session idempotently."""

    def __init__(self, token_service: ITokenService) -> None:
        self._token_service = token_service

    def execute(self, refresh_token: str) -> dict:
        """Revoke the presented session without exposing whether it was valid."""
        self._token_service.revoke_refresh_token(refresh_token)
        return {"loggedOut": True}