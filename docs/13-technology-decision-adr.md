# Décision d'architecture : plateforme SaaS, Django modulaire et PostgreSQL

## Statut : accepté pour le SaaS — décisions révisables par ADR

## Contexte de la décision
Tu es développeur Python/Django et Rust, tu développeras probablement seul ou en petite équipe, sur plusieurs comptes GitHub. Tu m'as demandé un conseil honnête, pas une réponse qui te fait plaisir.

## Option A — Microservices polyglottes (un langage/framework par bounded context)
Ex : `order-detection` en Django, `rules-engine` en Rust, `crm` en Django, etc., chacun avec sa propre base de données, déployés séparément.

**Pourquoi cette option n'est pas retenue pour la phase actuelle :**
- Chaque service polyglotte = son propre pipeline CI/CD, son propre monitoring, sa propre gestion de version d'API interne, sa propre stratégie de migration DB. Pour un développeur seul (ou une petite équipe), c'est un multiplicateur de charge opérationnelle, pas de valeur produit.
- Le risque réel n'est pas technique, il est humain : tu vas passer plus de temps à maintenir la plomberie inter-services qu'à livrer les couches 2/3/4 que tes utilisateurs attendent.
- DDD et Clean Architecture ne demandent pas un déploiement séparé par contexte. La séparation logique (dossiers, modules, interfaces) suffit à obtenir testabilité, remplaçabilité et clarté sans payer le coût opérationnel des microservices.

## Option B — Monolithe modulaire en Django (retenu)

Un seul projet Django, où chaque bounded context (`identity`, `access_control`, `platform_connectors`, `rules_engine`, `backup`, `order_detection`, `crm`, `billing`) est une Django app distincte, structurée selon les couches domain/application/infrastructure/presentation.

**Pourquoi ce choix convient à un SaaS :**
- Une base transactionnelle PostgreSQL et un processus de déploiement commun; les workers restent séparés par rôle opérationnel.
- Django fournit l'ORM, les migrations et un écosystème maintenu; les règles métier restent indépendantes du framework.
- Les ports, événements et tests d'architecture protègent les frontières de contexte. Une extraction future reste possible par décision dédiée.

## Optimisation et extraction de performance

Aucun changement de langage ou service séparé n'est introduit sans mesure de charge démontrant un goulot d'étranglement et un ADR dédié. Les Use Cases restent indépendants de l'implémentation concrète de `IRuleEvaluator`.

## PostgreSQL : une base, tables préfixées par contexte

Décision réversible pour cette phase : une base PostgreSQL et un schéma `public`, avec des tables nommées `<app_label>_<aggregate_or_record>` (par exemple `crm_contacts`, `order_detection_orders`, `platform_connectors_messages`). Le routage Django vers des schémas natifs est abandonné pour l'instant : ses coûts de migration, permissions et transactions ne sont pas justifiés avant qu'une exigence d'isolation les rende nécessaires. Un ADR ultérieur pourra le réintroduire.

Les préfixes sont un mécanisme d'organisation, pas une frontière de sécurité PostgreSQL. La CI vérifie que toutes les tables portent le préfixe de leur app, qu'aucun modèle ne déclare de relation ORM (ForeignKey, OneToOne, ManyToMany) vers un autre bounded context, et que les contextes ne s'importent pas directement entre eux. Les échanges passent par des ports applicatifs exposés ou des événements Outbox.

## Résumé de la décision

| Aspect | Choix |
|---|---|
| Langage principal | Python (Django) |
| Base de données | PostgreSQL unique, schéma `public`, tables préfixées par contexte; schémas natifs reportés |
| Déploiement | Monolithe modulaire avec workers spécialisés |
| Langage secondaire | Aucun sans mesure de charge et ADR |
| Microservices | Non retenus maintenant; réévaluation par décision documentée |
