from uuid import UUID

from contexts.identity.infrastructure.persistence.models import MerchantRecord

class DjangoMerchantCountryReader:
    """Implement the shared merchant-country query from Identity-owned records."""

    def country_code_for(self, merchant_id: UUID) -> str | None:
        """Return the configured country needed to resolve a Rules Engine scope."""
        return MerchantRecord.objects.filter(id=merchant_id).values_list(
            "country", flat=True
        ).first()