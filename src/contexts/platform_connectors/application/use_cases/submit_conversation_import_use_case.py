from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID

from shared_kernel.application_exceptions import ValidationException
from shared_kernel.ports import IEntitlementReader
from ...domain.value_objects.import_consent import ImportConsent


@dataclass(frozen=True)
class SubmitConversationImportResult:
    import_id: UUID
    status: str
    duplicate: bool


class SubmitConversationImportUseCase:
    """Queue a consented, size-bounded conversation import (INV-IMP-01/02/04)."""

    def __init__(self, formats, imports, entitlements: IEntitlementReader, cipher, clock, max_bytes: int):
        self._formats = formats
        self._imports = imports
        self._entitlements = entitlements
        self._cipher = cipher
        self._clock = clock
        self._max_bytes = max_bytes

    def execute(self, merchant_id: UUID, format_code: str, content: str, consent_id: UUID,
                consent: bool, selected_range: dict) -> SubmitConversationImportResult:
        """Validate consent/configuration and enqueue encrypted content without parsing it inline."""
        if consent is not True or not selected_range:
            raise ValidationException("Explicit consent and a selected range are required.")
        consent_evidence = ImportConsent(
            consent_id=consent_id,
            selected_range=selected_range,
            given_at=self._clock.now_utc(),
        )
        if not self._entitlements.entitlements_for(merchant_id).get("manual_import", False):
            raise ValidationException("Manual conversation import is not enabled for this plan.")
        format_config = self._formats.find_active(format_code)
        if format_config is None:
            raise ValidationException("Unknown or inactive import format.")
        encoded = content.encode("utf-8")
        if not encoded or len(encoded) > self._max_bytes:
            raise ValidationException("Import content is empty or exceeds the configured size limit.")
        try:
            import json

            if format_config["parser_key"] == "json_messages_v1":
                value = json.loads(content)
                if not isinstance(value, dict) or not isinstance(value.get("messages"), list):
                    raise ValueError
            elif format_config["parser_key"] != "configured_lines_v1":
                raise ValueError
        except (ValueError, TypeError) as error:
            raise ValidationException("Import content does not match the configured format.") from error
        range_fingerprint = json.dumps(selected_range, sort_keys=True, separators=(",", ":"))
        digest = sha256(
            f"{format_code}:{format_config['version']}:{range_fingerprint}:".encode()
            + encoded
        ).hexdigest()
        import_id, created = self._imports.create_if_new({
            "merchant_id": merchant_id,
            "consent_id": consent_evidence.consent_id,
            "consent_given_at": consent_evidence.given_at,
            "selected_range": consent_evidence.selected_range,
            "format_code": format_code,
            "content_hash": digest,
            "encrypted_content": self._cipher.encrypt(content),
            "created_at": self._clock.now_utc(),
            "updated_at": self._clock.now_utc(),
        })
        return SubmitConversationImportResult(import_id, "queued", not created)
