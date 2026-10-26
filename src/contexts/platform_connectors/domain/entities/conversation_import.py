from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class ConversationImport:
    """Import job aggregate protecting the resumable lifecycle (INV-IMP-01/03)."""

    id: UUID
    merchant_id: UUID
    status: str
    next_message_index: int
    accepted_count: int
    rejected_count: int
    errors: list[str]
    updated_at: datetime

    def start(self, occurred_at: datetime) -> None:
        """Move queued work to processing; only resumable work can restart (INV-IMP-03)."""
        if self.status not in {"queued", "processing"}:
            raise ValueError("Only queued or processing imports can run. INV-IMP-03")
        self.status = "processing"
        self.updated_at = occurred_at

    def record_message(self, index: int, accepted: bool, occurred_at: datetime) -> None:
        """Advance a successful batch cursor monotonically (INV-IMP-02/03)."""
        if self.status != "processing" or index < self.next_message_index:
            raise ValueError("Import cursor cannot move backwards. INV-IMP-03")
        self.next_message_index = index + 1
        self.accepted_count += int(accepted)
        self.updated_at = occurred_at

    def complete(self, rejected_count: int, errors: list[str], occurred_at: datetime) -> None:
        """Set a terminal state after the whole configured input has been examined (INV-IMP-03)."""
        if self.status != "processing":
            raise ValueError("Only processing imports can complete. INV-IMP-03")
        self.rejected_count = rejected_count
        self.errors = errors
        self.status = "completed_with_errors" if errors else "completed"
        self.updated_at = occurred_at

    def fail(self, error: str, occurred_at: datetime) -> None:
        """Record a terminal configuration/format failure without source content (INV-IMP-04)."""
        if self.status not in {"queued", "processing"}:
            raise ValueError("Terminal imports cannot fail again. INV-IMP-03")
        self.status = "failed"
        self.errors = [error]
        self.updated_at = occurred_at
