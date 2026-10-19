from dataclasses import dataclass

from shared_kernel.application_exceptions import ValidationException
from ..ports.plan_admin_repository import IPlanAdminRepository


class InvalidPlanDefinitionException(ValidationException):
    error_code = "INVALID_PLAN_DEFINITION"


ENTITLEMENT_KEYS = {
    "max_connections",
    "sync_mode",
    "history_days",
    "dormant_money_detail",
    "reminder_modes",
    "outbound_monthly_cap",
    "max_segments",
    "bulk_messages",
    "max_managed_merchants",
    "export_enabled",
}


@dataclass(frozen=True)
class UpsertPlanResult:
    code: str
    is_active: bool
    display_order: int


class UpsertPlanUseCase:
    """Create or update one plan definition through the authorized admin route."""

    def __init__(self, repository: IPlanAdminRepository) -> None:
        self._repository = repository

    def execute(
        self,
        code: str,
        is_active: bool,
        display_order: int,
        entitlements: dict[str, object] | None = None,
    ) -> UpsertPlanResult:
        if not code or len(code) > 32 or display_order < 0:
            raise InvalidPlanDefinitionException()
        for key, value in (entitlements or {}).items():
            if key not in ENTITLEMENT_KEYS or not _valid_entitlement(key, value):
                raise InvalidPlanDefinitionException()
            if key == "export_enabled" and value is not True:
                raise InvalidPlanDefinitionException()
        result = self._repository.upsert_plan(
            code, is_active, display_order, entitlements or {}
        )
        return UpsertPlanResult(result.code, result.is_active, result.display_order)


def _valid_entitlement(key: str, value: object) -> bool:
    if key in {"max_connections", "history_days", "outbound_monthly_cap", "max_segments", "max_managed_merchants"}:
        return isinstance(value, int) and not isinstance(value, bool) and value >= -1
    if key in {"dormant_money_detail", "bulk_messages", "export_enabled"}:
        return isinstance(value, bool)
    if key == "sync_mode":
        return isinstance(value, str) and bool(value)
    if key == "reminder_modes":
        return isinstance(value, list) and all(isinstance(mode, str) for mode in value)
    return False