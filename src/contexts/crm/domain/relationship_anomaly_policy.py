from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .exceptions import InvalidRelationshipAnomalyPolicyException


@dataclass(frozen=True)
class RelationshipAnomalyPolicy:
    """Configured parameters for CRM relationship anomaly detection (INV-CRM-05).

    Values are supplied by the application configuration port; this domain object
    validates them but never defines defaults or merchant-specific settings.
    """

    min_purchases: int
    anomaly_multiplier: Decimal
    min_inactivity_days: int

    def __post_init__(self) -> None:
        """Reject unusable configured values instead of silently normalizing them."""
        try:
            multiplier = Decimal(str(self.anomaly_multiplier))
        except (InvalidOperation, ValueError) as error:
            raise InvalidRelationshipAnomalyPolicyException(
                "Anomaly multiplier must be a positive finite number."
            ) from error

        if (
            isinstance(self.min_purchases, bool)
            or not isinstance(self.min_purchases, int)
            or self.min_purchases < 2
            or not multiplier.is_finite()
            or multiplier <= 0
            or isinstance(self.min_inactivity_days, bool)
            or not isinstance(self.min_inactivity_days, int)
            or self.min_inactivity_days < 0
        ):
            raise InvalidRelationshipAnomalyPolicyException(
                "Anomaly policy values are outside their valid ranges."
            )

        object.__setattr__(self, "anomaly_multiplier", multiplier)