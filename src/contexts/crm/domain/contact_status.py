from enum import StrEnum


class ContactStatus(StrEnum):
    """Lifecycle state of a Contact identity, including its audit tombstone."""

    ACTIVE = "active"
    MERGED = "merged"