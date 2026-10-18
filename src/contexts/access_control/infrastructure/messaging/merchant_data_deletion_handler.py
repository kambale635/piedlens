"""Module: contexts/access_control/infrastructure/messaging/merchant_data_deletion_handler.py
Context: Access Control
Role: translate MerchantDataDeleted Redis envelopes into the local purge use case.
"""

from uuid import UUID

from piedlens_platform.di.container import ApplicationContainer


def handle_merchant_data_deleted(envelope: dict) -> None:
    """Dispatch Backup deletion requests to Access Control's local purge (INV-AC-06, INV-BK-06)."""
    if envelope.get("producedBy") != "backup" or envelope.get("eventType") != "MerchantDataDeleted":
        return
    payload = envelope["payload"]
    ApplicationContainer.purge_access_control_merchant_data().execute(
        event_id=UUID(str(envelope["eventId"])),
        merchant_id=UUID(str(payload["merchant_id"])),
    )