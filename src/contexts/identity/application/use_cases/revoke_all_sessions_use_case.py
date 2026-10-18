from uuid import UUID

from ..ports.identity_ports import ITokenService


class RevokeAllSessionsUseCase:
    """Revoke every refresh and access session owned by one authenticated user."""

    def __init__(self, token_service: ITokenService) -> None:
        self._token_service = token_service

    def execute(self, acting_user_id: UUID) -> dict:
        """Revoke sessions for the principal supplied by authenticated middleware."""
        return {
            "revokedSessionCount": self._token_service.revoke_all_sessions(acting_user_id)
        }