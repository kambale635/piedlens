from uuid import UUID

from shared_kernel.application_exceptions import ResourceNotFoundException
from shared_kernel.ports.merchant_currency_reader import IMerchantCurrencyReader

from ..persistence.models import MerchantRecord


class DjangoMerchantCurrencyReader(IMerchantCurrencyReader):
    """Expose only the configured currency required by other contexts via a shared port."""

    def currency_for(self, merchant_id: UUID) -> str:
        record = MerchantRecord.objects.filter(id=merchant_id).only("currency").first()
        if record is None:
            raise ResourceNotFoundException("Merchant was not found.")
        return record.currency