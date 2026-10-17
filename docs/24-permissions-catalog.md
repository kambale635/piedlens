# Catalogue des permissions

Ce catalogue est dérivé des chaînes de permission effectivement déclarées avec `@requires_permission` dans les routes de l'application.

| Permission | Contexte | Routes protégées |
|---|---|---|

Aucune permission applicative n'est actuellement déclarée: le dépôt ne contient pas encore de routes de présentation/API. Les futures routes métier doivent déclarer leur permission avec `@requires_permission("<permission>" )`; `PermissionMiddleware` refuse par défaut toute route non publique sans permission explicite ou sans `IPermissionChecker` configuré.

Mettre ce catalogue à jour dans le même changement que chaque route protégée. Ne pas ajouter de permission sans usage réel.
