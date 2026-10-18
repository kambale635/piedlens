from uuid import UUID

from django.db.models import QuerySet

from .django_message_content_cipher import DjangoMessageContentCipher
from ..persistence.models import MessageRecord


class DjangoBackupMessageReader:
    """Expose normalized message deltas to Backup without importing that context (INV-TR-04)."""

    def __init__(self, content_cipher=None) -> None:
        self._content_cipher = content_cipher or DjangoMessageContentCipher()

    def read_messages(self, connection_id: UUID, since=None) -> list[dict]:
        """Return serializable messages for one connection after the prior snapshot."""
        records: QuerySet = MessageRecord.objects.filter(platform_connection_id=connection_id)
        if since is not None:
            records = records.filter(received_at__gt=since)
        messages = list(
            records.order_by("received_at", "id").values(
                "id",
                "external_message_id",
                "external_sender_id",
                "display_name",
                "text_content",
                "received_at",
            )
        )
        for message in messages:
            ciphertext = message["text_content"]
            plaintext = self._content_cipher.decrypt(ciphertext)
            if plaintext == ciphertext and "." not in ciphertext:
                message["text_content"] = self._content_cipher.encrypt(plaintext)
                MessageRecord.objects.filter(id=message["id"]).update(
                    text_content=message["text_content"]
                )
            else:
                message["text_content"] = plaintext
        return messages