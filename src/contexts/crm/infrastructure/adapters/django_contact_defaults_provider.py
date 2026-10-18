from uuid import UUID

from shared_kernel.ports.merchant_currency_reader import IMerchantCurrencyReader
from shared_kernel.value_objects.money import Money

from ...application.ports.contact_defaults import IContactDefaultsProvider


class DjangoContactDefaultsProvider(IContactDefaultsProvider):
    """Resolve CRM currency defaults through a shared-kernel Identity port."""

    def __init__(self, currency_reader: IMerchantCurrencyReader) -> None:
        self._currency_reader = currency_reader

    def initial_total_spent(self, merchant_id: UUID) -> Money:
        return Money(0, self.primary_currency(merchant_id))

    def primary_currency(self, merchant_id: UUID) -> str:
        return self._currency_reader.currency_for(merchant_id)