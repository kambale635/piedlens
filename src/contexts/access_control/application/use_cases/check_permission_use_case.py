from uuid import UUID

from ..ports.access_control_ports import IAccessControlRepository, IPermissionCache


class CheckPermissionUseCase:
    """Resolve scoped grants through the short-lived permission cache (INV-AC-01/03/05)."""

    def __init__(self, roles: IAccessControlRepository, cache: IPermissionCache) -> None:
        self.roles = roles
        self.cache = cache

    def execute(self, user_id: UUID, permission: str, scope) -> dict:
        """Check global or merchant-scoped grants without comparing role names."""
        scope_type, scope_id = self._scope(scope)
        scope_key = str(scope_id) if scope_id else "global"
        cached = self.cache.get(user_id, permission, scope_key)
        if cached is not None:
            return {"allowed": cached}
        allowed = permission in self.roles.permissions_for(user_id, scope_type, scope_id)
        self.cache.set(user_id, permission, scope_key, allowed)
        return {"allowed": allowed}

    @staticmethod
    def _scope(scope) -> tuple[str, UUID | None]:
        if scope in (None, "global"):
            return "global", None
        return "merchant", UUID(str(scope))