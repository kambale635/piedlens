from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ImportConsent:
    """Immutable evidence of merchant, purpose, range, and consent time (INV-IMP-01)."""

    consent_id: UUID
    selected_range: dict
    given_at: datetime

    def __post_init__(self) -> None:
        """Reject an empty consent scope before any import content is processed (INV-IMP-01)."""
        if not self.selected_range:
            raise ValueError("Import consent requires an explicit selected range. INV-IMP-01")
