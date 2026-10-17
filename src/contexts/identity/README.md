# Identity

Owns merchant registration and subscription-plan identity data.

References: [docs/02-domain-model.md](../../../docs/02-domain-model.md) and [docs/13-technology-decision-adr.md](../../../docs/13-technology-decision-adr.md).

Use Cases: see [docs/25-context-identity.md](../../../docs/25-context-identity.md) and the Identity contracts in [docs/15-use-cases-catalog.md](../../../docs/15-use-cases-catalog.md).

Tests: `docker compose run --rm django python manage.py test tests.unit.identity`.