"""Django model registration for the CRM infrastructure layer."""

from .infrastructure.models import (
	ContactRecord,
	OutboxEventRecord,
	ProcessedMessageRecord,
	RelationshipAnomalyNotificationRecord,
)

__all__ = [
	"ContactRecord",
	"OutboxEventRecord",
	"ProcessedMessageRecord",
	"RelationshipAnomalyNotificationRecord",
]