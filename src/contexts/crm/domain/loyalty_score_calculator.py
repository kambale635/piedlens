from typing import Protocol

from .contact import Contact
from .loyalty_score import LoyaltyScore


class ILoyaltyScoreCalculator(Protocol):
    """Domain service port for merchant-configured CRM loyalty scoring."""

    def calculate(self, contact: Contact) -> LoyaltyScore:
        """Calculate a loyalty score from the current contact and purchase profile."""