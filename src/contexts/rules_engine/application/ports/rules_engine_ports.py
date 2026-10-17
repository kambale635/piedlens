from typing import Protocol
from uuid import UUID

from ...domain.entities.rule_set import RuleSet


class IRuleSetRepository(Protocol):
    """Persistence port for Rules Engine-owned RuleSet aggregates."""

    def find_by_scope(self, scope: str) -> RuleSet | None: ...
    def save(self, rule_set: RuleSet) -> None: ...


class IRulesEngineUnitOfWork(Protocol):
    """Transaction boundary for one RuleSet/evaluation and its Outbox marker."""

    def __enter__(self) -> "IRulesEngineUnitOfWork": ...
    def __exit__(self, exception_type, exception, traceback) -> bool | None: ...


class IRulesEngineOutbox(Protocol):
    """Rules Engine-owned event Outbox port (INV-TR-02)."""

    def add(self, event: object) -> None: ...


class IProcessedEventRepository(Protocol):
    """Consumer idempotency ledger for MessageReceived and correction events (INV-TR-03)."""

    def has_processed(self, event_id: UUID, consumer_name: str) -> bool: ...
    def mark_processed(self, event_id: UUID, consumer_name: str) -> None: ...