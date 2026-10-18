"""Module: contexts/order_detection/infrastructure/messaging/merchant_data_deletion_handler.py
Context: Order Detection
Role: translate MerchantDataDeleted Redis envelopes into the local purge use case.
"""

from uuid import UUID

from piedlens_platform.di.container import ApplicationContainer


def handle_merchant_data_deleted(envelope: dict) -> bool | None:
    """Dispatch Backup deletion requests to Order Detection's local purge (INV-OD-08)."""
    if envelope.get("producedBy") != "backup" or envelope.get("eventType") != "MerchantDataDeleted":
        return None
    payload = envelope["payload"]
    return ApplicationContainer.purge_order_detection_merchant_data().execute(
        event_id=UUID(str(envelope["eventId"])),
        merchant_id=UUID(str(payload["merchant_id"])),
    )