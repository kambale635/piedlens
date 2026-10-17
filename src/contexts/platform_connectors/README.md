# Platform Connectors

Integrates external messaging platforms and translates inbound messages into normalized domain events. The local gateway is a deterministic mock; provider SDKs are not configured.

Reference: [docs/09-context-platform-connectors.md](../../../docs/09-context-platform-connectors.md).

Use Cases: ConnectPlatformUseCase, SyncMessagesUseCase, HandleIncomingWebhookUseCase, and RefreshTokensUseCase in [docs/15-use-cases-catalog.md](../../../docs/15-use-cases-catalog.md#contexte-platform-connectors).

Use Cases: `ConnectPlatformUseCase`, `SyncMessagesUseCase`, `HandleIncomingWebhookUseCase`, and `RefreshTokensUseCase`; scheduled sync is isolated per connection. `IConnectionUsageReader` is exposed via `shared_kernel/ports` and implemented by this context for Identity.

Security: tokens use AES-256-GCM and webhook requests require a configured per-platform HMAC secret. Configure `PLATFORM_TOKEN_ENCRYPTION_KEY`, `WHATSAPP_WEBHOOK_SECRET`, and `INSTAGRAM_WEBHOOK_SECRET` via environment variables.

Tests: `python manage.py test tests.unit.platform_connectors tests.integration.platform_connectors`.