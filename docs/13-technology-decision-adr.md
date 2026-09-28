# Décision d'architecture : choix technologique (Python/Django, Rust, mono vs polyglotte)

## Statut : décidé — à ne pas remettre en question avant le post-MVP (évite le syndrome "on recommence tout")

## Contexte de la décision
Tu es développeur Python/Django et Rust, tu développeras probablement seul ou en petite équipe, sur plusieurs comptes GitHub. Tu m'as demandé un conseil honnête, pas une réponse qui te fait plaisir.

## Option envisagée A — Microservices polyglotte (un langage/framework par bounded context)
Ex : `order-detection` en Django, `rules-engine` en Rust, `crm` en Django, etc., chacun avec sa propre base de données, déployés séparément.

**Pourquoi je le déconseille au MVP**, malgré que ce soit "propre" sur le papier :
- Chaque service polyglotte = son propre pipeline CI/CD, son propre monitoring, sa propre gestion de version d'API interne, sa propre stratégie de migration DB. Pour un développeur seul (ou une petite équipe), c'est un multiplicateur de charge opérationnelle, pas de valeur produit.
- Le risque réel n'est pas technique, il est humain : tu vas passer plus de temps à maintenir la plomberie inter-services qu'à livrer les couches 2/3/4 que tes utilisateurs attendent.
- DDD et Clean Architecture ne demandent **pas** un déploiement séparé par contexte. La séparation logique (dossiers, modules, interfaces) suffit à obtenir tous les bénéfices (testabilité, remplaçabilité, clarté) sans payer le coût opérationnel des microservices.

## Option envisagée B — Monolithe modulaire en Django (RECOMMANDÉ pour le MVP)

Un seul projet Django, où chaque bounded context (`rules_engine`, `platform_connectors`, `backup`, `order_detection`, `crm`) est une **Django app** distincte, structurée en interne selon les 4 couches (domain/application/infrastructure/presentation) décrites dans `05-module-structure.md`.

**Pourquoi c'est le bon choix maintenant :**
- Une seule base de données PostgreSQL, une seule migration, un seul déploiement, un seul monitoring — tu vas vite, tu livres vite, exactement ce que tu demandais dès le début ("pas bloquant, très rapide").
- Django te donne l'ORM, l'admin, l'auth, les migrations gratuitement — tu n'en as pas besoin en Rust au MVP.
- La séparation en couches strictes (voir `06-copilot-instructions.md`, règle 1 et 6) protège déjà des frontières de contexte, **même dans un seul repo/process**. Tu gardes la possibilité d'extraire un contexte en service séparé plus tard, exactement parce que les interfaces (ports) sont déjà en place — c'est le vrai bénéfice de Clean Architecture, pas le déploiement séparé.
- Un seul langage à maintenir dans les prompts Copilot, sur tous tes comptes = cohérence garantie, zéro risque de dérive entre deux sessions qui utiliseraient des conventions différentes.

## Où Rust a sa place — et seulement là (V2, pas MVP)

Rust n'est pas écarté, il est **positionné au bon endroit** : comme moteur d'évaluation à l'intérieur du contexte `Rules Engine`, appelé en sous-processus ou service interne séparé, **uniquement si/quand** le volume de messages à évaluer en temps réel devient un vrai goulot d'étranglement mesuré (pas supposé) en production.

Concrètement : `IRuleEvaluator` (voir `08-context-rules-engine.md`) reste l'interface stable côté Django. Le jour où tu as la preuve (métriques réelles) que l'évaluation Python est trop lente à l'échelle, tu écris une implémentation Rust exposée via un petit service HTTP/gRPC interne, et tu changes **uniquement** l'implémentation concrète injectée — zéro changement ailleurs dans le système, grâce au Dependency Inversion Principle déjà en place. C'est l'exemple même d'une extension qui ne casse rien (OCP).

**Ne fais pas ce choix avant d'avoir des utilisateurs payants et une vraie mesure de charge.** Optimiser une brique qui n'est pas encore le goulot d'étranglement est le piège classique qui retarde un lancement.

## Base de données : une seule, pas une par contexte

Une base PostgreSQL unique, avec un **schéma par bounded context** (`rules_engine`, `platform_connectors`, `backup`, `order_detection`, `crm` — schémas PostgreSQL natifs, pas des bases séparées). Ça donne :
- L'isolation logique nécessaire (chaque contexte a ses propres tables, pas d'accès croisé direct)
- Les migrations restent gérables (Django migrations par app)
- Zéro complexité de transaction distribuée, zéro cohérence éventuelle à gérer au MVP

**Règle stricte, à faire respecter par Copilot** : aucune requête ORM dans le module `order_detection` ne doit joindre directement une table du schéma `crm`. La communication passe par les interfaces de repository + les événements, jamais par une jointure SQL cross-contexte, même si techniquement possible dans une base unique. C'est une discipline, pas une contrainte technique — donc à surveiller activement en revue de code.

## Résumé de la décision (à ne pas dévier sans raison mesurée)

| Aspect | Choix |
|---|---|
| Langage principal | Python (Django) |
| Base de données | PostgreSQL unique, schémas séparés par contexte |
| Déploiement | Monolithe modulaire, un seul process/repo au MVP |
| Rust | Réservé à une extraction ciblée du Rules Engine, en V2, seulement si mesure de charge le justifie |
| Microservices polyglotte complets | Rejeté pour le MVP — reconsidérable après traction commerciale prouvée |
