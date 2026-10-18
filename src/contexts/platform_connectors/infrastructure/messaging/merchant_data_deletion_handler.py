"""Module: contexts/platform_connectors/infrastructure/messaging/merchant_data_deletion_handler.py
Context: Platform Connectors
Role: translate MerchantDataDeleted Redis envelopes into the local purge use case.
"""

from uuid import UUID

from piedlens_platform.di.container import ApplicationContainer


def handle_merchant_data_deleted(envelope: dict) -> None:
    """Dispatch Backup deletion requests to local credential/message cleanup (INV-PC-05)."""
    if envelope.get("producedBy") != "backup" or envelope.get("eventType") != "MerchantDataDeleted":
        return
    payload = envelope["payload"]
    ApplicationContainer.purge_platform_connectors_merchant_data().execute(
        event_id=UUID(str(envelope["eventId"])),
        merchant_id=UUID(str(payload["merchant_id"])),
    )