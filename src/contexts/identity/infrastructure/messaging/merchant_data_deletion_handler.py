"""Module: contexts/identity/infrastructure/messaging/merchant_data_deletion_handler.py
Context: Identity
Role: translate MerchantDataDeleted Redis envelopes into the local purge use case.
"""

from uuid import UUID

from piedlens_platform.di.container import ApplicationContainer


def handle_merchant_data_deleted(envelope: dict) -> None:
    """Dispatch only Backup deletion requests to Identity's local purge (INV-BK-06, INV-TR-03)."""
    if envelope.get("producedBy") != "backup" or envelope.get("eventType") != "MerchantDataDeleted":
        return
    payload = envelope["payload"]
    ApplicationContainer.purge_identity_merchant_data().execute(
        event_id=UUID(str(envelope["eventId"])),
        merchant_id=UUID(str(payload["merchant_id"])),
    )