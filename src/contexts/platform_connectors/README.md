# Platform Connectors

Integrates external messaging platforms and translates inbound messages into domain events.

Reference: [docs/09-context-platform-connectors.md](../../../docs/09-context-platform-connectors.md).

Use Cases: ConnectPlatformUseCase, SyncMessagesUseCase, HandleIncomingWebhookUseCase, and RefreshTokensUseCase in [docs/15-use-cases-catalog.md](../../../docs/15-use-cases-catalog.md#contexte-platform-connectors).

Tests: `docker compose run --rm django python manage.py test tests.unit.platform_connectors`.