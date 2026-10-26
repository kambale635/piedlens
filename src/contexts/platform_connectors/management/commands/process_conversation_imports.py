import hashlib
from datetime import datetime, timezone
from uuid import UUID

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone as django_timezone

from contexts.platform_connectors.application.services.import_format_parser import ImportFormatParser
from contexts.platform_connectors.infrastructure.adapters.django_message_content_cipher import DjangoMessageContentCipher
from contexts.platform_connectors.infrastructure.persistence.django_import_format_reader import DjangoImportFormatReader
from contexts.platform_connectors.infrastructure.persistence.django_platform_outbox import DjangoPlatformConnectorsOutbox
from contexts.platform_connectors.infrastructure.persistence.models import ConversationImportRecord, ImportFormatRecord, MessageRecord
from contexts.platform_connectors.domain.events.platform_events import MessageReceived
from contexts.platform_connectors.domain.entities.conversation_import import ConversationImport


class Command(BaseCommand):
    help = "Process queued consented conversation imports in resumable message transactions."

    def handle(self, *args, **options):
        parser = ImportFormatParser()
        cipher = DjangoMessageContentCipher()
        outbox = DjangoPlatformConnectorsOutbox(cipher)
        processed = 0
        for task in ConversationImportRecord.objects.filter(status__in=["queued", "processing"]).order_by("created_at", "id"):
            job = ConversationImport(
                task.id, task.merchant_id, task.status, task.next_message_index,
                task.accepted_count, task.rejected_count, list(task.errors), task.updated_at,
            )
            format_data = DjangoImportFormatReader().find_active(task.format_code)
            if format_data is None:
                job.fail("Import format is no longer active.", django_timezone.now())
                task.status, task.errors, task.updated_at = job.status, job.errors, job.updated_at
                task.save(update_fields=["status", "errors", "updated_at"])
                continue
            try:
                content = cipher.decrypt(task.encrypted_content)
                messages = parser.parse(content, format_data["parser_key"], format_data["config"])
            except (ValueError, TypeError) as error:
                job.fail(str(error), django_timezone.now())
                task.status, task.errors, task.updated_at = job.status, job.errors, job.updated_at
                task.save(update_fields=["status", "errors", "updated_at"])
                continue

            selected_range = task.selected_range
            start_at = _range_boundary(selected_range.get("from"), end=False)
            end_at = _range_boundary(selected_range.get("to"), end=True)
            messages = [
                message for message in messages
                if (start_at is None or message["received_at"] >= start_at)
                and (end_at is None or message["received_at"] <= end_at)
            ]

            job.start(django_timezone.now())
            task.status = job.status
            task.save(update_fields=["status"])
            errors = list(task.errors)
            for index in range(task.next_message_index, len(messages)):
                item = messages[index]
                digest = hashlib.sha256(
                    f"{item['external_sender_id']}:{item['external_message_id']}:{item['received_at'].isoformat()}".encode()
                ).hexdigest()
                message_id = UUID(bytes=hashlib.sha256(f"{task.id}:{digest}".encode()).digest()[:16])
                with transaction.atomic():
                    _, created = MessageRecord.objects.get_or_create(
                        platform_connection_id=task.id,
                        external_message_id=digest,
                        defaults={
                            "id": message_id,
                            "merchant_id": task.merchant_id,
                            "external_sender_id": item["external_sender_id"],
                            "display_name": item["display_name"],
                            "text_content": cipher.encrypt(item["text_content"]),
                            "received_at": item["received_at"],
                        },
                    )
                    if created:
                        outbox.add(MessageReceived(
                            merchant_id=task.merchant_id,
                            platform_connection_id=task.id,
                            message_id=message_id,
                            external_message_id=digest,
                            external_sender_id=item["external_sender_id"],
                            display_name=item["display_name"],
                            text_content=item["text_content"],
                            received_at=item["received_at"],
                        ))
                with transaction.atomic():
                    locked_task = ConversationImportRecord.objects.select_for_update().get(id=task.id)
                    if index < locked_task.next_message_index:
                        continue
                    locked_task.next_message_index = index + 1
                    locked_task.accepted_count += int(created)
                    locked_task.updated_at = django_timezone.now()
                    job.record_message(index, created, locked_task.updated_at)
                    locked_task.save(update_fields=["next_message_index", "accepted_count", "updated_at"])
                    task.next_message_index = locked_task.next_message_index
                    task.accepted_count = locked_task.accepted_count
                processed += 1
            job.complete(len(errors), errors, django_timezone.now())
            task.status, task.rejected_count = job.status, job.rejected_count
            task.errors, task.updated_at = job.errors, job.updated_at
            task.save(update_fields=["status", "rejected_count", "errors", "updated_at"])
        self.stdout.write(f"Processed {processed} imported message(s).")


def _range_boundary(value, end):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        from datetime import date, time

        parsed_date = date.fromisoformat(str(value))
        parsed = datetime.combine(parsed_date, time.max if end else time.min)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
