# Identity

Owns merchant registration and subscription-plan identity data.

References: [docs/02-domain-model.md](../../../docs/02-domain-model.md) and [docs/13-technology-decision-adr.md](../../../docs/13-technology-decision-adr.md).

Use Cases: RegisterMerchantUseCase and ChangeSubscriptionPlanUseCase in [docs/15-use-cases-catalog.md](../../../docs/15-use-cases-catalog.md#contexte-identity--access).

Tests: `docker compose run --rm django python manage.py test tests.unit.identity`.