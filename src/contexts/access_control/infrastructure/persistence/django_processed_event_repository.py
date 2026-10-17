from .models import ProcessedEventRecord


class DjangoProcessedEventRepository:
    def has_processed(self, event_id, consumer_name):
        return ProcessedEventRecord.objects.filter(
            event_id=event_id, consumer_name=consumer_name
        ).exists()

    def mark_processed(self, event_id, consumer_name):
        ProcessedEventRecord.objects.get_or_create(
            event_id=event_id,
            consumer_name=consumer_name,
        )