"""Django model registration for the CRM infrastructure layer."""

from .infrastructure.persistence.models import (
	BulkMessageCampaignRecord,
	BulkMessageRecipientRecord,
	ContactRecord,
	OutboxEventRecord,
	ProcessedMessageRecord,
	RelationshipAnomalyNotificationRecord,
	SegmentRecord,
)

__all__ = [
	"BulkMessageCampaignRecord",
	"BulkMessageRecipientRecord",
	"ContactRecord",
	"OutboxEventRecord",
	"ProcessedMessageRecord",
	"RelationshipAnomalyNotificationRecord",
	"SegmentRecord",
]