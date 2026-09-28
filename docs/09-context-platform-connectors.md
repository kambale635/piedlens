# Bounded Context : Platform Connectors

## Rôle
Isoler toute la complexité et la volatilité des API externes (WhatsApp Business API, Meta Graph API, futures plateformes) derrière des interfaces stables, pour que le reste du système ne dépende jamais d'un détail d'implémentation d'une plateforme précise.

## Interfaces (ports) — respect strict de l'Interface Segregation Principle

```
interface IMessageFetcher {
  fetchNewMessages(connection: PlatformConnection, since: DateTime): Message[]
}

interface IMessageSender {
  sendMessage(connection: PlatformConnection, recipientId: string, content: MessageContent): SendResult
}

interface IMediaDownloader {
  downloadMedia(connection: PlatformConnection, mediaId: string): MediaFile
}

interface IAccountHealthChecker {
  checkAccountStatus(connection: PlatformConnection): AccountHealthStatus
}
```
Chaque connecteur (`WhatsAppConnector`, `InstagramConnector`) implémente uniquement les interfaces pertinentes pour ses capacités réelles. Exemple : si une future plateforme ne permet pas l'envoi programmatique de messages (lecture seule), son connecteur n'implémente pas `IMessageSender` — pas de méthode qui lève une exception "non supporté" (violation ISP à éviter absolument, voir `03-solid-principles.md`).

## Use Cases

### `SyncMessagesUseCase`
Déclenché par un job planifié (fréquence selon le plan d'abonnement du merchant — configurable, pas codé en dur).
1. Pour chaque `PlatformConnection` active, appeler `IMessageFetcher.fetchNewMessages`
2. Pour chaque nouveau message : persister en base (traçabilité brute), publier `MessageReceived [EVT]`
3. Mettre à jour `lastSyncedAt`

### `HandleIncomingWebhookUseCase`
Pour les plateformes supportant les webhooks temps réel (préférable à la synchronisation périodique quand disponible) :
1. Valider la signature du webhook (sécurité — chaque plateforme a son mécanisme, ex: `X-Hub-Signature-256` pour Meta)
2. Traduire le payload spécifique à la plateforme vers le modèle `Message` interne unifié (Anti-Corruption Layer, voir ci-dessous)
3. Publier `MessageReceived [EVT]`

## Anti-Corruption Layer (ACL) — concept DDD important ici

Chaque plateforme a son propre format de données (JSON WhatsApp ≠ JSON Instagram). Le connecteur contient un **mapper dédié** qui traduit le format externe vers le modèle de domaine interne (`Message`, `Contact` partiel). **Aucun champ brut d'une API externe ne doit fuiter au-delà de la couche infrastructure de ce contexte.** C'est ce qui protège le reste du système d'un changement d'API externe (Meta change son format ? Seul le mapper de ce contexte change).

## Gestion des tokens et de la sécurité

- `accessToken` stocké chiffré (`EncryptedToken` Value Object, voir `02-domain-model.md`)
- Rafraîchissement automatique des tokens avant expiration (job planifié dédié `RefreshTokensUseCase`)
- En cas d'expiration/révocation détectée : publier `PlatformConnectionExpired [EVT]` → déclenche une notification au merchant (contexte Identity ou notification transverse)

## Cas limites à gérer explicitement dans le code

- Rate limiting imposé par la plateforme externe → utiliser `IRateLimiter` (voir `04-tech-stack-infrastructure.md`) avant chaque appel sortant, avec backoff exponentiel en cas de 429 reçu de l'API externe
- Panne temporaire de l'API externe → ne pas faire échouer toute la synchronisation, isoler l'échec par connexion (`try/catch` par `PlatformConnection`, pas un seul `try/catch` global)
- Messages dupliqués (webhook renvoyé deux fois par la plateforme, cas fréquent) → idempotence via `externalMessageId` unique en base, contrainte d'unicité au niveau DB, pas seulement applicatif

## Tests attendus

- Tests d'intégration avec les vrais formats de payload de chaque plateforme (fixtures JSON réelles, anonymisées)
- Test spécifique d'idempotence (même webhook reçu 2 fois → un seul `Message` créé)
- Test du mapper ACL isolément (garantit que la traduction reste correcte si le connecteur évolue)
