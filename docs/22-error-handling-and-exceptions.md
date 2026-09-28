# Gestion des erreurs & exceptions — standard unique

## Principe : une hiérarchie d'exceptions claire, un seul point de traduction vers HTTP

Trois niveaux d'exceptions, jamais mélangés :

```
DomainException (abstraite)
  ├── InvalidOrderTransitionException      (Order Detection)
  ├── PlanConnectionLimitReachedException  (Identity)
  ├── InsufficientPrivilegeException       (Access Control)
  └── ... une exception nommée par invariant violé (voir INV-XX-NN)

ApplicationException (abstraite)
  ├── ResourceNotFoundException
  ├── ValidationException
  └── ConcurrencyConflictException

InfrastructureException (abstraite)
  ├── ExternalPlatformUnavailableException  (WhatsApp/Meta API down)
  ├── RateLimitExceededException
  └── StorageException
```

**Règle** : le domaine ne lève que des `DomainException`, jamais une exception technique (`ConnectionError`, `TimeoutError` bruts) — l'infrastructure traduit ses propres erreurs techniques en `InfrastructureException` avant qu'elles ne remontent au-delà de sa couche, pour que l'application et le domaine ne dépendent jamais d'un détail technique externe (cohérent avec Dependency Inversion, `03-solid-principles.md`).

## Mapping exception → HTTP (unique point de traduction : `ExceptionHandlingMiddleware`, voir `21-middleware-layer.md`)

| Exception | Code HTTP | errorCode |
|---|---|---|
| `ValidationException` | 400 | `VALIDATION_ERROR` |
| `AuthenticationRequiredException` | 401 | `UNAUTHENTICATED` |
| `InsufficientPrivilegeException` | 403 | `FORBIDDEN` |
| `ResourceNotFoundException` | 404 | `NOT_FOUND` |
| `InvalidOrderTransitionException` (et toute `DomainException` de conflit d'état) | 409 | `INVALID_STATE_TRANSITION` (ou nom spécifique) |
| `PlanConnectionLimitReachedException` (et toute règle métier violée hors conflit d'état) | 422 | `BUSINESS_RULE_VIOLATION` |
| `InvalidRelationshipAnomalyPolicyException` | 422 | `INVALID_RELATIONSHIP_ANOMALY_POLICY` |
| `RateLimitExceededException` | 429 | `RATE_LIMIT_EXCEEDED` |
| `ExternalPlatformUnavailableException` | 503 | `EXTERNAL_SERVICE_UNAVAILABLE` |
| Toute exception non prévue/inconnue | 500 | `INTERNAL_ERROR` (jamais de détail technique exposé au client, voir §3) |

## Format de réponse d'erreur — unique, identique sur toute l'API

```json
{
  "errorCode": "INVALID_STATE_TRANSITION",
  "message": "La commande ne peut pas passer de 'paid_and_delivered' à 'pending_payment'.",
  "correlationId": "uuid",
  "details": { "currentStatus": "paid_and_delivered", "requestedStatus": "pending_payment" }
}
```
- `message` : phrase claire, compréhensible par un développeur frontend (ou l'utilisateur final selon le canal), jamais une trace technique brute
- `correlationId` : toujours présent, permet de retrouver la requête exacte dans les logs (voir `RequestIdMiddleware`, `21-middleware-layer.md`)
- `details` : optionnel, structuré, jamais de texte libre imprévisible

## Règle de sécurité stricte sur les erreurs 500

Une exception non prévue (`500 INTERNAL_ERROR`) ne renvoie **jamais** la stack trace, le message d'exception brut, ni aucun détail d'implémentation au client — uniquement `errorCode: "INTERNAL_ERROR"` et le `correlationId`. Le détail complet est loggé côté serveur (avec le `correlationId` pour le retrouver), jamais exposé côté client. Fuiter une stack trace est une vulnérabilité de sécurité classique (révèle la structure interne, les versions de librairies, parfois des secrets) — jamais toléré, même en développement une fois que l'habitude de coder est prise.

## Règle pour le domaine (rappel, cohérent avec `03-solid-principles.md`)

Chaque `DomainException` doit :
- Porter un nom explicite qui décrit l'invariant violé (pas `BusinessException` générique)
- Citer dans son docstring l'identifiant `INV-XX-NN` concerné (voir `17-documentation-standards.md`)
- Être levée **depuis l'agrégat lui-même** quand elle protège un invariant d'agrégat (ex : `Order.change_status()` lève `InvalidOrderTransitionException`), jamais depuis un Use Case qui ferait la vérification lui-même

## Règle pour l'infrastructure (résilience)

- Tout appel à une API externe (WhatsApp, Meta) est entouré d'un `try/except` qui traduit toute erreur technique en `ExternalPlatformUnavailableException`, avec retry/backoff exponentiel géré à ce niveau, jamais remonté tel quel au domaine.
- Toute erreur d'un consommateur d'événement (voir `14-event-driven-architecture.md`) qui échoue après plusieurs tentatives doit être routée vers une **dead-letter queue** dédiée par contexte, avec alerte, plutôt que perdue silencieusement.

## Logging des exceptions — cohérence avec l'audit (voir `21-middleware-layer.md`)

- `DomainException` et `ApplicationException` : loggées en niveau `WARNING` (ce sont des cas métier normaux, pas des bugs)
- `InfrastructureException` : loggées en niveau `ERROR` (indique un problème technique réel à surveiller)
- Toute exception non prévue (500) : loggée en niveau `CRITICAL`, avec alerte immédiate si un système de monitoring est branché (à prévoir dès que le volume d'utilisateurs le justifie)

## Tests attendus

- Chaque `DomainException` doit avoir un test qui vérifie qu'elle est bien levée dans le cas invariant approprié (voir tests listés dans chaque fichier de contexte)
- Test du middleware de gestion d'exception : vérifie qu'aucune exception non `DomainException`/`ApplicationException`/`InfrastructureException` ne fuit une stack trace dans la réponse HTTP
