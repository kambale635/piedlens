# Décisions d’implémentation Afrique

Les décisions D1–D8, règles T1–T10, invariants et phases de livraison sont consolidés dans [`41-implementation-decisions.md`](41-implementation-decisions.md), qui prévaut sur les documents Afrique 30–39 en cas de différence.

# 📐 Documentation d'architecture — SentinelCommerce
> Nom de code provisoire du projet (renomme-le dans tous les fichiers avant de démarrer)

Ce dossier est la **source de vérité** du projet. Il doit être placé à la racine du repo (`/docs`), et le fichier `.github/copilot-instructions.md` (fourni séparément) doit y faire référence explicitement. GitHub Copilot (et tout développeur, humain ou IA, sur n'importe lequel de tes comptes) doit lire ces fichiers avant de générer du code — ils font foi sur toute suggestion contradictoire de Copilot.

## Point d'entrée le plus rapide

Si tu n'ouvres que 3 fichiers avant de commencer à coder : `18-product-vision-and-objectives.md` (pourquoi), `16-business-invariants-and-rules.md` (les règles à ne jamais violer), `15-use-cases-catalog.md` (contrats et index). Pour les contextes Afrique, ouvrir aussi le document de contexte référencé par 15, qui fait foi pour le contrat détaillé.

## Ordre de lecture recommandé

| # | Fichier | Rôle |
|---|---|---|
| 1 | `01-architecture-overview.md` | Vue stratégique : Clean Architecture + DDD, bounded contexts, context map |
| 2 | `02-domain-model.md` | Modèle de domaine : agrégats, entités, value objects, événements de domaine |
| 3 | `03-solid-principles.md` | Application concrète des 5 principes SOLID sur CE projet, avec exemples |
| 4 | `04-tech-stack-infrastructure.md` | Choix techniques : Redis, base de données, queues, justification |
| 5 | `05-module-structure.md` | Arborescence de dossiers/projets respectant les couches Clean Architecture |
| 6 | `06-copilot-instructions.md` | À copier dans `.github/copilot-instructions.md` — règles strictes pour toute génération de code |
| 7 | `07-api-contracts.md` | Contrats d'API par contexte, formats de requête/réponse |
| 8 | `08-context-rules-engine.md` | Bounded Context : Moteur de règles (le cœur adaptable du système) |
| 9 | `09-context-platform-connectors.md` | Bounded Context : Connecteurs de plateformes (WhatsApp, Instagram...) |
| 10 | `10-context-backup.md` | Bounded Context : Sauvegarde automatique |
| 11 | `11-context-order-detection.md` | Bounded Context : Détection de commandes / "argent qui dort" |
| 12 | `12-context-crm.md` | Bounded Context : Mini-CRM automatique |
| 13 | `13-technology-decision-adr.md` | Décision tranchée : Python/Django monolithe modulaire, PostgreSQL unique, où Rust a sa place |
| 14 | `14-event-driven-architecture.md` | Architecture événementielle complète : publisher par contexte, Outbox Pattern, Redis Streams, idempotence |
| 15 | `15-use-cases-catalog.md` | **Catalogue exhaustif de tous les Use Cases**, avec contrat d'entrée/sortie exact, préconditions, erreurs, événements — à consulter avant chaque implémentation |
| 16 | `16-business-invariants-and-rules.md` | **Tous les invariants métier consolidés en un seul endroit**, identifiants `INV-XX-NN` référencés partout ailleurs |
| 17 | `17-documentation-standards.md` | Gabarits de docstring/commentaire niveau senior, format de commit |
| 18 | `18-product-vision-and-objectives.md` | Vision produit complète, objectifs, roadmap des 5 couches, modèle économique — le "pourquoi" du projet |
| 19 | `19-cahier-des-charges-fonctionnel.md` | Cahier des charges fonctionnel détaillé des couches MVP (sauvegarde, argent qui dort, CRM) |
| 20 | `20-context-access-control.md` | Bounded Context : **Rôles & permissions (RBAC/PBAC configurable)**, admin gère tout sans toucher au code |
| 21 | `21-middleware-layer.md` | **Couche Middleware complète** : auth, tenant isolation, permissions, rate limiting, audit, exceptions |
| 22 | `22-error-handling-and-exceptions.md` | Hiérarchie d'exceptions, mapping HTTP, format de réponse d'erreur unique |
| 23 | `23-shared-kernel-value-objects.md` | Value Objects partagés entre tous les contextes (Money, téléphone, identifiants...) |
| 24 | `24-permissions-catalog.md` | Catalogue des permissions, généré par Copilot à partir des routes protégées |
| 25 | `25-context-identity.md` | Bounded Context : Identity (User, Merchant, connexion, inscription) |
| 30 | `30-africa-market-vision-and-principles.md` | Vision et principes du commerce social africain, pilote RDC |
| 31 | `31-country-packs-and-localization.md` | CountryPack, RDC et configuration des marchés |
| 32 | `32-context-mobile-money.md` | Instructions, preuves et rapprochement Mobile Money |
| 33 | `33-context-currency-rates.md` | Taux merchant, RateSnapshot et conversion explicite |
| 34 | `34-context-catalog-inventory.md` | Catalogue, variantes, unités et stock |
| 35 | `35-context-pricing-negotiation.md` | Prix, remises et négociation sous contrôle vendeur |
| 36 | `36-context-supplier-network.md` | Fournisseurs, vérification humaine et commandes de gros |
| 37 | `37-context-logistics.md` | Zones, livreurs, remise et rapprochement COD |
| 38 | `38-context-storefront-status-studio.md` | Cartes Status manuelles et mini-boutique publique |
| 39 | `39-whatsapp-onboarding-and-compliance.md` | Onboarding, mode sans API et conformité à vérifier |
| 40 | `40-roadmap-and-validation-gates.md` | Phases et portes de validation du pilote |

## Règle d'or pour toi (le concepteur produit, non-développeur)

Tu n'as pas besoin de savoir coder pour utiliser ces fichiers correctement. Ta seule responsabilité :

1. Ne jamais laisser Copilot générer du code **avant** d'avoir donné le fichier de contexte pertinent (ex : demande "génère l'agrégat Order en respectant `docs/11-context-order-detection.md`").
2. Ne jamais accepter une suggestion Copilot qui **contourne** une couche décrite dans `01-architecture-overview.md` (ex : un contrôleur API qui appelle directement la base de données — interdit).
3. Si Copilot te propose quelque chose qui n'est décrit nulle part ici, arrête-toi et redemande une clarification (à moi ou à un dev) avant d'accepter — ne jamais laisser une IA improviser l'architecture.

## Pourquoi cette approche (Clean Architecture + DDD + SOLID) et pas "coder vite"

Tu as demandé une approche "une bonne fois pour toute", pas d'itérations bâclées. Ces trois piliers garantissent :

- **Clean Architecture** → le cœur métier (règles, détection, CRM) ne dépend d'aucune techno externe (Redis, WhatsApp API, base de données). Tu peux changer de fournisseur SMS, de base de données, ou d'API WhatsApp dans 2 ans sans réécrire la logique métier.
- **DDD (Domain-Driven Design)** → chaque "couche" du produit (sauvegarde, argent qui dort, CRM) devient un **bounded context** isolé, avec son propre langage et ses propres règles, ce qui permet à plusieurs développeurs (ou plusieurs sessions Copilot, sur plusieurs comptes) de travailler dessus sans se marcher dessus.
- **SOLID** → chaque classe a une seule responsabilité, le code est extensible sans être modifié à chaque nouvelle plateforme/pays/langue — exactement ton exigence de "s'adapter à tout, rien de codé en dur".

## Statut de complétude

- [x] Architecture stratégique
- [x] Modèle de domaine
- [x] Infrastructure (Redis, DB, queues)
- [x] Standards de code / instructions Copilot
- [x] Contrats d'API
- [x] 5 bounded contexts détaillés
- [x] Décision technologique tranchée (Python/Django vs Rust vs polyglotte)
- [x] Architecture événementielle complète (publisher, Outbox, idempotence)
- [x] Catalogue complet des Use Cases avec paramètres exacts
- [x] Invariants métier consolidés (un seul document de référence)
- [x] Standards de documentation/commentaires niveau senior
- [x] Vision produit et objectifs (le "pourquoi" complet du projet)
- [x] Cahier des charges fonctionnel des couches MVP
- [x] Gestion des rôles/permissions (configurable, sans code en dur)
- [x] Couche Middleware complète (auth, tenant, permissions, rate limit, audit)
- [x] Gestion des erreurs/exceptions uniforme
- [x] Shared Kernel des Value Objects communs
- [ ] Diagrammes de séquence détaillés (à ajouter en V2, une fois le MVP stabilisé)
- [ ] Tests d'acceptation (Gherkin) — à ajouter avant le développement de chaque user story

## Feuille de route d'implémentation (ordre recommandé, pour toi — pas une règle pour Copilot)

Ne demande jamais à Copilot de générer un contexte entier d'un coup — un Use Case à la fois, en pointant vers `15-use-cases-catalog.md` (voir le gabarit de prompt qu'on a mis au point ensemble). Enchaîne les contextes dans cet ordre :

1. **Squelette + config** — structure de dossiers Django conforme à `05-module-structure.md`, `docker-compose.yml` (Django + PostgreSQL + Redis)
2. **Contexte `identity`** — le plus simple, valide que toute la structure (couches, injection de dépendances, tests) fonctionne avant de complexifier
3. **Contexte `access-control`** — les rôles/permissions doivent exister tôt, avant tout contexte métier, puisque la chaîne de middleware (`PermissionMiddleware`) protège toutes les routes dès leur création ; commence avec les rôles système par défaut (`Owner`, `Admin`, `Staff`) et un `IPermissionChecker` fonctionnel avant d'écrire le moindre contrôleur métier
4. **Couche Middleware transverse** (`21-middleware-layer.md`) — implémente la chaîne complète une fois, réutilisée par tous les contextes suivants
5. **Contexte `platform-connectors`** — commence par un connecteur mock (pas l'API WhatsApp réelle tout de suite) pour pouvoir tester les contextes suivants sans dépendre d'une intégration externe encore instable
6. **Contexte `rules-engine`**
7. **Contexte `order-detection`**
8. **Contexte `crm`**
9. **Contexte `backup`** — indépendant des autres, peut se faire en parallèle à n'importe quel moment après l'étape 2
10. **Event bus réel** (Outbox Pattern + Redis Streams, voir `14-event-driven-architecture.md`) — seulement une fois que chaque contexte existe isolément et est testé ; avant cette étape, les contextes peuvent communiquer via des appels directs temporaires en mode développement, à condition de les remplacer avant la mise en production

**Pourquoi cet ordre** : chaque étape valide la précédente sans dépendre d'une intégration externe fragile (API WhatsApp réelle) avant que le cœur du système ne soit prouvé fonctionnel.
