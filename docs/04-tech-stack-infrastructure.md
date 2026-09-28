# Stack technique & Infrastructure

## 1. Vue d'ensemble

| Besoin | Choix recommandé | Justification |
|---|---|---|
| Langage/Runtime | Node.js (TypeScript) ou C# (.NET) | Choisis celui où Copilot te donne les meilleures suggestions dans tes comptes — les deux supportent bien Clean Architecture. TypeScript recommandé si l'équipe est mixte front/back. |
| Base de données principale | PostgreSQL | Transactions ACID nécessaires pour les agrégats Order/Contact, support JSONB pour les configs de règles flexibles |
| Cache / données éphémères | Redis | Voir section 2 |
| File de messages / événements | Redis Streams (MVP) → RabbitMQ ou Kafka (scale) | Redis Streams suffit largement pour le volume initial, évite d'introduire une techno supplémentaire trop tôt |
| Stockage médias (images, captures d'écran) | Stockage objet compatible S3 (ex : Cloudflare R2, moins cher que S3 pur) | Coût faible, adapté au volume de captures d'écran/photos produits |
| Conteneurisation | Docker + Docker Compose (dev), Kubernetes ou simple VPS (prod MVP) | Ne pas sur-ingénierer l'infra avant d'avoir des utilisateurs payants |

## 2. Rôles précis de Redis dans ce système

Redis n'est **jamais** une source de vérité — toujours un accélérateur ou un mécanisme éphémère. La source de vérité reste PostgreSQL.

### 2.1 Cache de lecture
- Résultats de `SegmentMembershipCalculator` (recalcul coûteux) — TTL court (5-15 min), invalidé sur tout événement `ContactUpdated`.
- Profil `Merchant` (lu à chaque requête API) — TTL 10 min.

### 2.2 Bus d'événements (Redis Streams ou Pub/Sub)
- Canal `platform.message.received` → consommé par `Rules Engine`
- Canal `rules.evaluation.completed` → consommé par `Order Detection` et `CRM`
- Canal `order.status.changed` → consommé par notifications push

**Important architecturalement** : les Use Cases publient des événements via une interface `IEventPublisher` (domaine/application), jamais un appel direct au client Redis — encore une application du Dependency Inversion Principle.

### 2.3 Rate limiting
- Limiter les appels sortants vers l'API WhatsApp/Meta (respect des quotas imposés par ces plateformes) via un compteur Redis avec expiration (`INCR` + `EXPIRE`), encapsulé derrière une interface `IRateLimiter`.

### 2.4 Verrouillage distribué (locks)
- Éviter les doublons de traitement si plusieurs workers traitent le même message en parallèle (`SETNX` avec expiration) — encapsulé derrière `IDistributedLock`.

### 2.5 File d'attente de jobs différés
- Planification des relances (`Reminder.scheduledFor`) — l'application persiste Reminder + `ReminderScheduled` dans PostgreSQL via l'outbox; le relay déclenche ensuite un job Redis. Aucun Use Case ne fait de dual-write PostgreSQL/Redis. La bibliothèque de jobs concrète sera sélectionnée côté infrastructure lorsque le worker sera implémenté.

## 3. Schéma d'infrastructure (déploiement MVP)

```
                    ┌─────────────┐
                    │   API Gateway │ (reçoit requêtes REST + webhooks)
                    └──────┬───────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
     ┌───────────┐  ┌───────────┐  ┌────────────┐
     │ App Server │  │ App Server │  │ Worker(s)   │ (traitement async des événements)
     │ (stateless)│  │ (stateless)│  │             │
     └─────┬─────┘  └─────┬─────┘  └──────┬──────┘
           │              │               │
           └──────┬───────┴───────┬───────┘
                   ▼               ▼
           ┌──────────────┐ ┌──────────┐
           │  PostgreSQL   │ │  Redis    │
           │  (vérité)     │ │(cache/bus)│
           └──────────────┘ └──────────┘
                   │
                   ▼
           ┌──────────────┐
           │ Stockage objet│ (médias)
           └──────────────┘
```

## 4. Sécurité infrastructure (non négociable, voir aussi `06-copilot-instructions.md`)

- Tous les tokens d'accès aux plateformes (`accessToken` du `PlatformConnection`) chiffrés au repos (AES-256), jamais en clair en base — même en développement.
- Variables sensibles (clés API, secrets DB) exclusivement via variables d'environnement / secret manager, jamais commitées, même dans un fichier `.env.example` rempli.
- Connexions PostgreSQL et Redis exclusivement en TLS en production.
- Logs applicatifs : jamais de contenu de message client en clair dans les logs (RGPD-like) — logguer des identifiants, pas du contenu.

## 5. Environnements

| Environnement | But |
|---|---|
| local (Docker Compose) | développement, chaque compte GitHub/Copilot doit pouvoir le lancer en une commande (`docker compose up`) |
| staging | tests d'intégration avant chaque déploiement |
| production | MVP mono-région pour commencer (choisir la région la plus proche du marché cible prioritaire) |

## 6. Ce qu'on NE fait PAS au MVP (pour aller vite, sans dette technique cachée)

- Pas de microservices séparés en déploiement — les bounded contexts sont séparés **en code** (modules), pas forcément en déploiement physique au MVP. La séparation logique permet de les extraire en services séparés plus tard sans réécriture, si le besoin de scale apparaît (c'est tout l'intérêt de l'architecture choisie).
- Pas de Kafka au MVP — Redis Streams suffit, migration possible plus tard car les Use Cases dépendent de `IEventPublisher`, pas directement de Redis.
- Pas de multi-région au MVP.
