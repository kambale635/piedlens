from typing import Protocol
from ..entities.contact import Contact
from ..value_objects.loyalty_score import LoyaltyScore


class ILoyaltyScoreCalculator(Protocol):
    """Domain service port for merchant-configured CRM loyalty scoring."""

    def calculate(self, contact: Contact, primary_currency: str) -> LoyaltyScore:
        """Calculate loyalty using only the merchant's primary currency (INV-CRM-08)."""