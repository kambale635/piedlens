from django.core.management.base import BaseCommand
from django.db import transaction

from contexts.platform_connectors.domain.value_objects.encrypted_token import EncryptedToken
from contexts.platform_connectors.infrastructure.adapters.django_aes_token_cipher import (
    DjangoAesTokenCipher,
)
from contexts.platform_connectors.infrastructure.persistence.models import PlatformConnectionRecord


class Command(BaseCommand):
    """Re-encrypt each stored platform token independently with the active key."""

    help = "Re-encrypt stored platform tokens with the active versioned key."

    def handle(self, *args, **options):
        cipher = DjangoAesTokenCipher()
        rotated_count = 0
        connection_ids = list(
            PlatformConnectionRecord.objects.order_by("id").values_list("id", flat=True)
        )
        for connection_id in connection_ids:
            with transaction.atomic():
                record = PlatformConnectionRecord.objects.select_for_update().get(
                    id=connection_id
                )
                encrypted_token = EncryptedToken(record.encrypted_access_token)
                if cipher.key_version(encrypted_token) == cipher.active_key_version:
                    continue
                plaintext = cipher.decrypt(encrypted_token)
                record.encrypted_access_token = cipher.encrypt(plaintext).value
                record.save(update_fields=["encrypted_access_token"])
                rotated_count += 1
        self.stdout.write(f"Rotated {rotated_count} platform token(s).")