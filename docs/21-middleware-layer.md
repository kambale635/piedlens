# Couche Middleware — niveau SaaS professionnel

## Rôle
La couche Middleware est la porte d'entrée de toute requête HTTP, avant même qu'elle n'atteigne un contrôleur. C'est ici que se font les vérifications transverses qu'on ne veut **jamais** répéter manuellement dans chaque Use Case ou contrôleur. Un contrôleur qui vérifie lui-même l'authentification ou les permissions est une violation d'architecture (voir `06-copilot-instructions.md`).

## Chaîne de middleware, dans l'ordre d'exécution strict

```
Requête HTTP entrante
   │
   ▼
[1] RequestIdMiddleware        → génère/propage un correlationId unique (traçabilité bout en bout, voir 14-event-driven-architecture.md)
   │
   ▼
[2] ExceptionHandlingMiddleware → englobe tout ce qui suit, capture toute exception non gérée (voir 22-error-handling-and-exceptions.md)
   │
   ▼
[3] AuthenticationMiddleware   → vérifie le token/session, résout le userId, rejette 401 si absent/invalide
   │
   ▼
[4] TenantIsolationMiddleware  → résout le merchantId courant depuis le token/route, l'attache à la requête (jamais lu depuis le body/params librement, pour éviter qu'un utilisateur usurpe un autre merchantId)
   │
   ▼
[5] PermissionMiddleware       → résout la Permission requise pour la route (déclarée explicitement par le contrôleur, jamais devinée), appelle IPermissionChecker.can(), rejette 403 si refusé
   │
   ▼
[6] RateLimitMiddleware        → applique IRateLimiter (voir 04-tech-stack-infrastructure.md §2.3), rejette 429 si dépassé
   │
   ▼
[7] AuditLoggingMiddleware     → journalise l'action (userId, permission vérifiée, scope, résultat) — AVANT d'atteindre le contrôleur, pour tracer même les tentatives refusées
   │
   ▼
Contrôleur → Use Case → Réponse
```

## Détail de chaque middleware

### [1] RequestIdMiddleware
Génère un `correlationId` (UUID) si absent de l'en-tête `X-Correlation-Id`, sinon le propage. Attaché à toute la chaîne de logs et d'événements de domaine émis pendant le traitement de cette requête.

### [2] ExceptionHandlingMiddleware
Le seul endroit du système qui convertit une exception en réponse HTTP. Voir `22-error-handling-and-exceptions.md` pour le mapping complet exception → code HTTP → format de réponse. **Aucun contrôleur ne doit avoir de `try/catch` qui formate une réponse d'erreur lui-même** — il laisse l'exception remonter, ce middleware s'en charge de façon uniforme.

### [3] AuthenticationMiddleware
Valide le token (JWT ou session Django selon implémentation), résout `userId`. Si absent ou invalide → `401 UNAUTHENTICATED` immédiatement, sans atteindre les middlewares suivants.

### [4] TenantIsolationMiddleware
Résout `merchantId` de façon fiable (depuis le token/claims, ou depuis l'URL pour les routes explicitement multi-tenant type Agency) — **jamais** en faisant confiance à un `merchantId` fourni librement dans le body de la requête par le client, ce qui permettrait à un utilisateur malveillant de cibler les données d'un autre merchant.

### [5] PermissionMiddleware
Chaque route déclare explicitement la `Permission` requise (annotation/décorateur, jamais implicite) :
```python
@requires_permission("order.update_status")
class OrderStatusController(APIView):
    ...
```
Le middleware lit cette déclaration, appelle `IPermissionChecker.can(userId, permission, scope)` (contexte Access Control, `20-context-access-control.md`). Refus → `403 FORBIDDEN`, avec le nom de la permission manquante dans les logs (jamais dans la réponse au client, pour ne pas exposer la structure interne des permissions à un attaquant).

### [6] RateLimitMiddleware
Protège l'API elle-même (pas seulement les appels sortants vers WhatsApp/Meta, voir `04-tech-stack-infrastructure.md`) contre les abus — limite par utilisateur et par IP, configurable par plan d'abonnement (un plan Agency a des limites plus hautes qu'un plan Starter).

### [7] AuditLoggingMiddleware
Journalise systématiquement : `correlationId`, `userId`, `merchantId` (scope), `permission vérifiée`, `résultat (allowed/denied)`, `route`, `timestamp`. Stocké séparément des logs applicatifs classiques (table/flux dédié `audit_log`), jamais mélangé aux logs de debug — nécessaire pour toute investigation de sécurité ou conformité future.

## Règle stricte pour Copilot

Aucune vérification d'authentification, de tenant, ou de permission ne doit être écrite manuellement dans un contrôleur ou un Use Case — la chaîne de middleware s'en charge intégralement, une fois. Un Use Case reçoit un `userId` et un `merchantId` déjà validés et fiables, jamais à revalider lui-même. S'il faut une vérification métier supplémentaire au-delà de la permission générique (ex : "ce contact appartient-il bien à ce merchant"), c'est un invariant de domaine (voir `16-business-invariants-and-rules.md`), pas une responsabilité du middleware.

## Configuration par environnement

| Middleware | Dev | Staging | Production |
|---|---|---|---|
| RateLimitMiddleware | désactivé ou seuils larges | seuils réels | seuils réels stricts |
| AuditLoggingMiddleware | actif, logs locaux | actif | actif, rétention longue définie par la politique de conformité |
| AuthenticationMiddleware | actif (jamais désactivé, même en dev) | actif | actif |


## Routes publiques et refus par défaut

Toute route doit déclarer explicitement soit `@requires_permission("<resource>.<action>")`, soit `@public_route` (réservé à l'inscription, la connexion et le rafraîchissement de token). Une route sans aucune des deux déclarations est **refusée par défaut** (`403`), jamais laissée ouverte par oubli. Les routes publiques passent quand même par `RequestIdMiddleware`, `ExceptionHandlingMiddleware`, `RateLimitMiddleware` et `AuditLoggingMiddleware`.
