"""Django model registration for the Order Detection infrastructure layer."""

from .infrastructure.models import (
    CandidateOrderCreationLockRecord,
    DetectionCandidateRecord,
    OrderRecord,
    OutboxEventRecord,
    ProcessedEventRecord,
    ReminderRecord,
)

__all__ = [
    "CandidateOrderCreationLockRecord",
    "DetectionCandidateRecord",
    "OrderRecord",
    "OutboxEventRecord",
    "ProcessedEventRecord",
    "ReminderRecord",
]