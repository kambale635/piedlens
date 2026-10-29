from typing import Protocol
from uuid import UUID


class IPaymentProviderRegistry(Protocol):
    def require(self, provider_code: str, capability: type): ...


class ICheckoutInitiator(Protocol):
    def initiate(self, *, attempt_id: UUID, amount_minor: int, currency: str, idempotency_key: str) -> dict: ...


class IPaymentWebhookVerifier(Protocol):
    def verify(self, provider_code: str, raw_body: bytes, signature: str, timestamp: str) -> bool: ...


class IPaymentStatusReader(Protocol):
    def status_for(self, provider_reference: str) -> dict: ...


class IPaymentProofParser(Protocol):
    def parse(self, provider_code: str, payload: dict) -> dict: ...


class IPayoutSender(Protocol):
    def send(self, account_id: UUID, amount_minor: int, currency: str, idempotency_key: str) -> dict: ...


class IRefundIssuer(Protocol):
    def issue(self, provider_code: str, provider_reference: str, idempotency_key: str) -> dict: ...


class IPaymentRepository(Protocol):
    def create_attempt(self, attempt, idempotency_key: str, request_hash: str): ...
    def find_for_update(self, attempt_id: UUID): ...
    def find_by_provider_event(self, provider_code: str, event_id: str): ...
    def save_attempt(self, attempt) -> None: ...
    def save_provider_event(self, provider_code: str, event_id: str, payload_hash: str) -> bool: ...


class IPaymentUnitOfWork(Protocol):
    def __enter__(self): ...
    def __exit__(self, exception_type, exception, traceback): ...


class IPaymentOutbox(Protocol):
    def add(self, event: object) -> None: ...


class IPayableReader(Protocol):
    def payable(self, merchant_id: UUID, payable_type: str, payable_id: UUID, options: dict) -> dict: ...


class IPaymentRouteReader(Protocol):
    def find_route(self, country: str, currency: str, method: str) -> dict | None: ...


class ISubscriptionPayableReader(Protocol):
    def subscription_payable(self, merchant_id: UUID, plan_code: str, period_days: int) -> dict | None: ...


class IPaymentRouteAdminRepository(Protocol):
    def upsert(self, route: dict) -> None: ...


class IPaymentPriceReader(Protocol):
    def subscription_price(self, merchant_id: UUID, plan_code: str, period_days: int) -> dict | None: ...
