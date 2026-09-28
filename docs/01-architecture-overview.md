# Architecture Overview — Clean Architecture + DDD

## 1. Principe directeur

**La règle de dépendance** (Clean Architecture, Uncle Bob) : les dépendances de code ne pointent que vers l'intérieur. Le domaine métier ne connaît **rien** de Redis, de PostgreSQL, de l'API WhatsApp, ou de FastAPI/Express. C'est l'inverse : l'infrastructure dépend du domaine, jamais le contraire.

```
┌───────────────────────────────────────────────────┐
│  INFRASTRUCTURE (la plus externe, la plus volatile) │
│  Redis, PostgreSQL, WhatsApp API, Meta Graph API,    │
│  files de messages (RabbitMQ/SQS), stockage objet    │
│  ┌─────────────────────────────────────────────┐    │
│  │  INTERFACE / PRESENTATION                     │    │
│  │  Contrôleurs REST, Webhooks entrants,          │    │
│  │  Jobs planifiés (cron), CLI                    │    │
│  │  ┌───────────────────────────────────────┐    │    │
│  │  │  APPLICATION (cas d'usage)              │    │    │
│  │  │  Use Cases / Application Services       │    │    │
│  │  │  Orchestrent le domaine, ne contiennent │    │    │
│  │  │  AUCUNE règle métier elles-mêmes        │    │    │
│  │  │  ┌─────────────────────────────────┐    │    │    │
│  │  │  │  DOMAIN (le cœur, invariant)      │    │    │    │
│  │  │  │  Agrégats, Entités, Value Objects │    │    │    │
│  │  │  │  Domain Events, Domain Services   │    │    │    │
│  │  │  │  ZÉRO dépendance externe          │    │    │    │
│  │  │  └─────────────────────────────────┘    │    │    │
│  │  └───────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────┘
```

**Règle stricte pour Copilot** : si une suggestion de code fait apparaître un `import` de librairie technique (Redis client, SDK WhatsApp, ORM) dans un fichier du dossier `domain/`, c'est une violation — refuser et redemander.

## 2. Les 4 couches, en détail

### 2.1 Domain (cœur)
Contient : Agrégats (Aggregate Roots), Entités, Value Objects, Domain Events, Domain Services (logique qui ne appartient à aucune entité seule), Repository **interfaces** (pas d'implémentation).
Ne contient jamais : appels réseau, SQL, dépendances à un framework.

### 2.2 Application (cas d'usage)
Contient : Use Cases (ex: `DetectPaymentFromMessageUseCase`), DTOs d'entrée/sortie, orchestration de plusieurs domain services, transactions.
Dépend de : Domain uniquement (via interfaces).
Ne contient jamais : logique métier elle-même (elle délègue au domaine), détails d'implémentation technique.

### 2.3 Infrastructure
Contient : implémentations concrètes des repository interfaces (ex: `PostgresOrderRepository`), clients Redis, adaptateurs API externes (WhatsApp, Meta), implémentations de file de messages.
Dépend de : Application + Domain (implémente leurs interfaces).

### 2.4 Interface / Presentation
Contient : contrôleurs HTTP, handlers de webhooks, jobs cron, CLI.
Rôle unique : traduire une requête externe en appel à un Use Case, et formatter la réponse. Aucune logique ici.

## 3. Approche DDD — Bounded Contexts (contexte map)

Le système est découpé en **contextes bornés** indépendants, chacun avec son propre langage ubiquitaire et son propre modèle de données. Ils communiquent par **événements de domaine** (pas par appels directs entre bases de données), ce qui permet de développer/déployer chaque contexte séparément.

```
┌────────────────────┐     événements      ┌──────────────────────┐
│  Identity & Access  │────────────────────▶│   Platform Connectors │
│  (User, Auth, Plan) │                     │  (WhatsApp, Instagram)│
└────────────────────┘                     └──────────┬────────────┘
                                                        │ MessageReceived
                                                        ▼
                                            ┌──────────────────────┐
                                            │    Rules Engine        │
                                            │ (contexte partagé/     │
                                            │  shared kernel)         │
                                            └──────────┬────────────┘
                     ┌──────────────────────┬──────────┴────────────┐
                     ▼                      ▼                       ▼
          ┌────────────────┐    ┌────────────────────┐   ┌──────────────┐
          │     Backup       │    │  Order Detection    │   │     CRM       │
          │   (sauvegarde)   │    │ (argent qui dort)    │   │  (mini-CRM)   │
          └────────────────┘    └────────────────────┘   └──────────────┘
```

### Pourquoi le Rules Engine est un "shared kernel" et non un bounded context comme les autres
Il est consommé par les 3 autres contextes métier (Backup n'en a pas vraiment besoin, mais Order Detection et CRM oui). Il expose une **interface stable** (`IRuleEvaluator`) que chaque contexte consomme sans connaître son implémentation interne. C'est le point d'extension principal pour "s'adapter à tout pays/langue" sans toucher aux autres contextes.

## 4. Communication inter-contextes

- **Synchrone** : uniquement via interfaces bien définies (ports), jamais d'accès direct à la base de données d'un autre contexte.
- **Asynchrone (préféré)** : via un bus d'événements (Redis Pub/Sub en MVP, migrable vers RabbitMQ/Kafka en scale). Exemple : `MessageReceivedEvent` publié par Platform Connectors, consommé par Rules Engine, qui publie ensuite `PaymentDetectedEvent`, consommé par Order Detection.

## 5. Pourquoi ce découpage sert ton exigence "s'adapter à tout"

- Ajouter une plateforme (TikTok Shop) = nouveau module dans `Platform Connectors`, zéro changement ailleurs.
- Ajouter un pays/langue = nouvelle configuration dans `Rules Engine`, zéro changement de code dans les autres contextes.
- Ajouter une 4e couche métier (radar produits gagnants, anti-arnaque) = nouveau bounded context, se branche sur les événements existants sans toucher à l'existant (principe Open/Closed, voir `03-solid-principles.md`).
