from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PlanAdminRecord:
    code: str
    is_active: bool
    display_order: int


@dataclass(frozen=True)
class PlanPriceAdminRecord:
    plan_code: str
    country: str
    currency: str
    period_days: int
    amount_minor: int
    is_active: bool


class IPlanAdminRepository(Protocol):
    """Persist plan definitions, entitlements, and localized prices in Billing."""

    def upsert_plan(
        self,
        code: str,
        is_active: bool,
        display_order: int,
        entitlements: dict[str, object],
    ) -> PlanAdminRecord: ...

    def upsert_price(
        self,
        plan_code: str,
        country: str,
        currency: str,
        period_days: int,
        amount_minor: int,
        is_active: bool,
    ) -> PlanPriceAdminRecord | None: ...