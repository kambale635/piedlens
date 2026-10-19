from shared_kernel.ports import IEntitlementReader

from ...application.dto.reminder_delivery import ReminderDeliveryMode


class DjangoReminderDeliveryPolicy:
    """Resolve reminder delivery exclusively from the merchant's Billing entitlements."""

    def __init__(self, entitlements: IEntitlementReader) -> None:
        self._entitlements = entitlements

    def mode_for(self, order):
        modes = self._entitlements.entitlements_for(order.merchant_id).get(
            "reminder_modes", []
        )
        if "api_send" in modes:
            return ReminderDeliveryMode.API_SEND
        return ReminderDeliveryMode.MANUAL_LINK