from uuid import UUID

from contexts.identity.application.use_cases.change_subscription_plan_use_case import (
    ChangeSubscriptionPlanUseCase,
)
from contexts.identity.application.ports.identity_ports import (
    IIdentityProcessedEventRepository,
    IIdentityUnitOfWork,
)


class ConsumePaymentSucceededUseCase:
    """Apply a verified subscription payment in a separate Identity transaction (INV-PAY-02/T1/T2)."""

    CONSUMER_NAME = "identity-payment-succeeded"

    def __init__(self, processed_events: IIdentityProcessedEventRepository,
                 unit_of_work: IIdentityUnitOfWork, change_plan: ChangeSubscriptionPlanUseCase):
        self._processed = processed_events
        self._unit_of_work = unit_of_work
        self._change_plan = change_plan

    def execute(self, event_id: UUID, merchant_id: UUID, plan_code: str):
        with self._unit_of_work:
            if self._processed.has_processed(event_id, self.CONSUMER_NAME):
                return {"outcome": "already_processed"}
            self._change_plan.change_in_current_transaction(merchant_id, plan_code)
            self._processed.mark_processed(event_id, self.CONSUMER_NAME)
        return {"outcome": "plan_changed", "planCode": plan_code}
