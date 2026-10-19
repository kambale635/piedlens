from uuid import uuid4

from shared_kernel.domain_exceptions import InvalidValueObjectException
from ...domain.entities.merchant import Merchant
from ...domain.events.identity_events import MerchantRegistered
from ...domain.value_objects.identity_values import CountryCode, CurrencyCode, LanguageCode
from ..exceptions.identity_exceptions import InvalidMerchantData
from ..ports.identity_ports import (
    IIdentityClock,
    IIdentityOutbox,
    IIdentityUnitOfWork,
    IMerchantRepository,
)


class CreateMerchantUseCase:
    """Create a Discovery Merchant and append its event atomically (INV-ID-01, INV-TR-02)."""

    def __init__(self, merchants: IMerchantRepository, unit_of_work: IIdentityUnitOfWork,
                 outbox: IIdentityOutbox, clock: IIdentityClock) -> None:
        self.merchants = merchants
        self.unit_of_work = unit_of_work
        self.outbox = outbox
        self.clock = clock

    def execute(self, acting_user_id, name: str, country: str,
                preferred_language: str, currency: str) -> dict:
        """Create the business account without storing membership in Identity (INV-ID-06)."""
        try:
            merchant = Merchant.register(
                uuid4(), name, CountryCode(country),
                LanguageCode(preferred_language), CurrencyCode(currency), self.clock.now_utc()
            )
        except (InvalidValueObjectException, ValueError) as error:
            raise InvalidMerchantData() from error
        with self.unit_of_work:
            self.merchants.save(merchant)
            self.outbox.add(MerchantRegistered(merchant.id, acting_user_id))
        return {"merchantId": merchant.id, "subscriptionPlan": merchant.subscription_plan}