"""Django model registration for the Order Detection infrastructure layer."""

from .infrastructure.persistence.models import (
    CandidateOrderCreationLockRecord,
    DetectionContactLockRecord,
    ContactReferenceRedirectRecord,
    DetectionCandidateRecord,
    OrderRecord,
    OutboxEventRecord,
    ProcessedEventRecord,
    ReminderRecord,
)

__all__ = [
    "CandidateOrderCreationLockRecord",
    "DetectionContactLockRecord",
    "ContactReferenceRedirectRecord",
    "DetectionCandidateRecord",
    "OrderRecord",
    "OutboxEventRecord",
    "ProcessedEventRecord",
    "ReminderRecord",
]