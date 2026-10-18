from shared_kernel.ports import IMerchantCountryReader, IMerchantPlanReader

from ...application.ports.channel_config import IChannelAvailability
from .models import ChannelConfigRecord


class DjangoChannelConfigReader(IChannelAvailability):
    """Resolve channel enablement from ChannelConfig and shared Identity read ports."""

    def __init__(
        self,
        merchant_plans: IMerchantPlanReader,
        merchant_countries: IMerchantCountryReader,
    ) -> None:
        self._merchant_plans = merchant_plans
        self._merchant_countries = merchant_countries

    def is_enabled_for_merchant(self, channel_code: str, merchant_id) -> bool:
        config = ChannelConfigRecord.objects.filter(code=channel_code, active=True).first()
        if config is None:
            return False
        plan = self._merchant_plans.plan_for(merchant_id)
        country = self._merchant_countries.country_code_for(merchant_id)
        if plan is None or country is None or not config.plan_flags.get(plan, False):
            return False
        return config.country_flags.get(country, True)