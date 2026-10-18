# Journal d'evolution du projet

Ce fichier conserve les decisions, documents consultes, fichiers crees ou modifies et prochaines etapes afin de faciliter la reprise du projet.
Mettre a jour ce journal a chaque etape importante.

## 2026-10-18 - Reprise apres interruption

- Etat initial : branche `main` a `9d89cef` (Outbox relay et Redis Streams deja committes); changements non committes deja presents concernant suppression merchant, S3, Compose et des adaptations connexes. Aucun changement existant n'a ete annule ni reinstalle.
- Environnement : `redis-cli ping` repond `PONG`; le venv existant `venv/` est utilise directement car le terminal outil n'avait pas son activation. Aucune dependance ni environnement n'a ete installe ou recree.
- Transport Redis valide : tests `test_outbox_relay` et `test_redis_stream_consumer`, 4/4. Le test Outbox verifie maintenant `PING` dans son setup et produit un echec explicite si Redis est inaccessible; l'injection `REDIS_URL=redis://localhost:1/0` confirme l'echec sans skip.
- Point de reprise confirme : le relay/consumer est termine; la suppression distribuee des donnees merchant reste la prochaine etape, ses handlers n'etant pas presents. Le stockage S3 et le Compose de deploiement restent ensuite a verifier.
- Identity — purge merchant terminee : le consumer `MerchantDataDeleted` supprime uniquement le `Merchant`, conserve les `User`, inscrit `(event_id, consumer_name)` et `MerchantDataPurged` atomiquement; handler d'enveloppe et migration ajoutes (INV-ID-07, INV-BK-06, INV-TR-01/03).
- Validation Identity : tests unitaires et integration du handler, 8/8; migrations appliquees par le test. Prochaine etape : purge locale idempotente Access Control, puis Platform Connectors, Rules Engine, Order Detection et CRM.
- Access Control — purge merchant terminee : suppression reprenable par RoleAssignment, conservation separee des identifiants d'audit, roles/assignations globaux non modifies, marqueur idempotent et `MerchantDataPurged` via Outbox (INV-AC-06, INV-BK-06, INV-TR-01/03).
- Validation Access Control : tests unitaires et integration 8/8; `makemigrations access_control --check --dry-run` sans changement. Prochaine etape : purge Platform Connectors.
- Platform Connectors — purge merchant terminee : connexions et tokens chiffres detruits avant les messages; chaque enregistrement a un checkpoint atomique. Les ecritures de message verrouillent et revalident la connexion pour empecher une recreation apres purge (INV-PC-05, INV-BK-06, INV-TR-01/03).
- Validation Platform Connectors : tests unitaires/integration 12/12; `makemigrations platform_connectors --check --dry-run` sans changement. Prochaine etape : purge Rules Engine.
- Rules Engine — purge merchant terminee : suppression reprenable uniquement du RuleSet `merchant:<id>`; les configurations pays/globales et les autres merchants restent intactes. Marqueur idempotent et `MerchantDataPurged` via Outbox (INV-RE-05, INV-BK-06, INV-TR-01/03).
- Validation Rules Engine : tests unitaires/integration 7/7; `makemigrations rules_engine --check --dry-run` sans changement. Prochaine etape : purge Order Detection.
- Order Detection — purge merchant terminee : Orders, Reminders, DetectionCandidates et redirections locales purges par enregistrement, transactions et checkpoints separes; marqueur idempotent et Outbox final (INV-OD-08, INV-BK-06, INV-TR-01/03). La documentation INV-OD-08 est alignee sur les redirections locales.
- Correction de wiring decouverte : les repositories Identity/Access Control et Rules Engine/Order Detection partagent des noms de classe; le composition root alias maintenant les deux implementations afin que les marqueurs restent dans leur contexte proprietaire.
- Validation Order Detection : unitaires 44/44, integration Django 14/14, `manage.py check` sans erreur et `makemigrations order_detection --check --dry-run` sans changement. Prochaine etape : purge CRM.
- CRM — purge merchant terminee : contacts et historique, segments, notifications d'anomalie, campagnes et journaux destinataires supprimes en transactions locales distinctes avec checkpoints; marqueur idempotent et `MerchantDataPurged` via Outbox (INV-CRM-09, INV-BK-06, INV-TR-01/03). Les documents 14/16 enumerent maintenant les campagnes et journaux.
- Validation CRM : tests unitaires/integration 63/63; `makemigrations crm --check --dry-run` sans changement; diagnostics sans erreur. Prochaine etape : brancher les six handlers dans la topologie Redis/Compose, puis verifier l'adaptateur S3 et le deploiement.

## 2026-10-17 - Reprise de la phase avant production

- Etat initial verifie : branche `main` a `7ea088f`; worktree sale avec changements interrompus concernant Redis Streams/Outbox, suppression merchant, S3 et configuration de déploiement. Aucun contenu préexistant n'a été réinitialisé.
- Redis local répond `PONG`. Le test d'intégration Redis utilise désormais `REDIS_URL` (défaut localhost), échoue explicitement si le serveur est indisponible et nettoie ses clés de test; il ne peut plus être ignoré silencieusement faute de variable.
- Transport Outbox/Redis Streams : relay multi-contextes, commandes relay/consumer, enveloppe versionnée, reprise `XAUTOCLAIM`, DLQ et migrations `next_attempt_at` présents. Ajout de tests intégration relay (publication réelle Outbox CRM vers Redis, succès, retry Redis) et consumer (reprise avant acquittement); validation ciblée 4/4.
- `manage.py check` et `makemigrations --check --dry-run` passent avec `config.test_settings`.
- Limites du jalon : garanties `SKIP LOCKED`/concurrence non vérifiées sur PostgreSQL; aucun test bout-en-bout du pipeline métier complet n'est exécuté. L'ancien venv `.venv` et Python système n'ont pas `redis`; l'environnement existant `venv/` contient `redis` et `boto3` et a été utilisé sans installation.
- Prochaine étape : terminer et tester la suppression merchant distribuée par bounded context. Les handlers `MerchantDataDeleted` ne sont pas présents malgré la topologie documentée. Ensuite vérifier l'adaptateur S3 et le déploiement Compose, corriger leurs écarts, puis effectuer une seule suite complète en fin de phase.

## 2026-10-17 - Reprise des contrats API et contextes

- CRM — `ListContactsUseCase` : terminé; contrat ajouté à 15, route `GET /contacts` (`contact.read`), tests pagination/scope.
- CRM — `CreateSegmentUseCase` : terminé; route `POST /segments` (`segment.create`).
- CRM — `GetSegmentMembersUseCase` : terminé; route paginée `GET /segments/{id}/members` (`contact.read`) et vérification merchant.
- CRM — `SendBulkMessageUseCase` : terminé; route `POST /segments/{id}/bulk-message` (`segment.bulk_message`) et vérification merchant.
- CRM — `MergeContactsUseCase` : terminé; route `POST /contacts/merge` (`contact.merge`), réponse 202.
- Order Detection — `GetDormantMoneyDashboardUseCase` : terminé; route `GET /dashboard/dormant-money` (`order.read`), totaux par devise.
- Order Detection — `UpdateOrderStatusUseCase` : terminé; route `PATCH /orders/{id}/status` (`order.update_status`), scope merchant revalidé.
- Order Detection — `ScheduleReminderUseCase` : terminé; route `POST /orders/{id}/reminders` (`order.remind`), délais configurables.
- Order Detection — `ListPendingDetectionCandidatesUseCase` : terminé; route `GET /detection-candidates` (`order.review`).
- Order Detection — `ValidateOrRejectDetectionUseCase` : terminé; route `POST /detection-candidates/{id}/decision` (`order.review`).
- Platform Connectors — `ConnectPlatformUseCase` : terminé avec gateway mock, AES-256-GCM et limite de plan; route `platform.connect`.
- Platform Connectors — `SyncMessagesUseCase` : terminé; job multi-connexion isole les erreurs (INV-PC-04), idempotence DB (INV-PC-03).
- Platform Connectors — `HandleIncomingWebhookUseCase` : terminé; webhooks publics HMAC avant parsing (INV-PC-02), idempotence par contrainte DB.
- Platform Connectors — `RefreshTokensUseCase` : terminé; token chiffré ou connexion expirée avec événement Outbox.
- Rules Engine — `EvaluateMessageUseCase` : terminé; consommateur idempotent, priorité merchant > pays > global, données de langue/devise/motifs configurables (INV-RE-01/02/04).
- Rules Engine — `UpdateRuleSetUseCase` : terminé; route `PUT /rule-sets/{scope}` (`rule_config.edit`), scopes global/pays exigent permission globale.
- Rules Engine — `AdjustRuleWeightFromCorrectionUseCase` : terminé; consommateur idempotent et ajustement borné à ±10 (INV-RE-03).
- Backup — `ListBackupsUseCase` : terminé; route `GET /backups` (`backup.read`).
- Backup — `GetBackupExportUseCase` : terminé; route `GET /backups/exports/{id}` (`backup.read`).
- Backup — `CreateSnapshotUseCase` : terminé; job incrémental, hash et consentement obligatoire (INV-BK-01/02/03).
- Backup — `RestoreFromSnapshotUseCase` : terminé; route `POST /backups/{id}/restore` (`backup.restore`), exports JSON/CSV et URL signée.
- Backup — `CheckAccountHealthUseCase` : terminé; job sans route, alertes via Outbox.
- Backup — `DeleteAllMerchantDataUseCase` : terminé; route `DELETE /merchants/{id}/data` (`merchant.delete_data`) avec jeton de double confirmation (INV-BK-04).
- Shared Kernel — `IConnectionUsageReader` : terminé; implémenté dans Platform Connectors et injecté à Identity pour INV-ID-03.
- Shared Kernel — ports de pays, consentement, données de sauvegarde et santé : terminés, sans import inter-contextes.
- Validation de cette reprise : 115 tests Django, 4 tests d'architecture; `makemigrations --check --dry-run` sans changement.

## 2026-10-17 - Identity, Access Control et politiques de routes

- Identity — `RegisterUserUseCase` : terminé, tests unitaires et parcours HTTP.
- Identity — `AuthenticateUserUseCase` : terminé, erreurs anti-énumération et hash Django.
- Identity — `RefreshAccessTokenUseCase` : terminé, refresh signé et vérification du statut utilisateur.
- Identity — `CreateMerchantUseCase` : terminé, événement Outbox transactionnel; appartenance non persistée dans Identity (INV-ID-06).
- Identity — `ChangeSubscriptionPlanUseCase` : implémenté; branchement au fournisseur d'usage/connecteur à finaliser avec Platform Connectors.
- Access Control — `CreateRoleUseCase` : terminé, permission validée contre les routes réelles et acteur tracé.
- Access Control — `UpdateRolePermissionsUseCase` : terminé, Outbox et invalidation du cache.
- Access Control — `AssignRoleToUserUseCase` : terminé, contrôle anti-auto-élévation par scope et audit.
- Access Control — `RevokeRoleFromUserUseCase` : terminé, audit et invalidation du cache.
- Access Control — `CheckPermissionUseCase` : terminé, scope global/merchant et cache TTL.
- Access Control — `AssignOwnerRoleOnMerchantRegisteredUseCase` : terminé, idempotence via assignation et `processed_events`.
- API Identity/Access Control : routes du contrat 07 ajoutées; CRM et Order Detection n'ont aucune route spécifiée dans 07.
- Middleware : marqueur explicite public/authentifié et refus par défaut testés.
- Platform Connectors, Rules Engine et Backup : à faire après lecture de leurs contrats contextuels; non implémentés dans cette étape.
- Outbox relay et publisher Redis : placeholders; blocants de mise en production.

## 2026-10-16 - Reprise de la structuration Clean Architecture

- Périmètre courant : réorganiser les couches par bounded context selon `docs/05-module-structure.md`, sans modifier les contrats métier.
- Order Detection — `DetectOrderUseCase` : comportement et tests existants; structure en cours.
- Order Detection — `CreateOrderFromPromotedDetectionUseCase` : comportement et tests existants; structure en cours.
- Order Detection — `UpdateOrderStatusUseCase` : comportement et tests existants; structure en cours.
- Order Detection — `GetDormantMoneyDashboardUseCase` : comportement et tests existants; structure en cours.
- Order Detection — `ScheduleReminderUseCase` : comportement et tests existants; structure en cours.
- Order Detection — `SendScheduledRemindersUseCase` : comportement et tests existants; structure en cours.
- Order Detection — `ValidateOrRejectDetectionUseCase` : comportement et tests existants; structure en cours.
- Order Detection — `ListPendingDetectionCandidatesUseCase` : comportement et tests existants; structure en cours.
- Order Detection — `ReassignContactReferencesFromContactMergedUseCase` : comportement et tests existants; structure en cours.
- Décision de placement : exceptions génériques et bases partagées restent dans `shared_kernel`; exceptions métier restent dans leur bounded context, rangées sous `exceptions/`.
- Étape suivante : déplacer les entités, repositories, value objects et événements Order Detection vers les sous-dossiers documentés, puis valider import Django, tests unitaires/intégration et frontières d'architecture.

### Order Detection — structure terminée

- Domain réorganisé conformément à `docs/05-module-structure.md` : `entities/`, `repositories/`, `value_objects/`, `exceptions/` et `events/`; les Use Cases, DTO (`application/dto`), ports applicatifs (`application/ports`) et adaptateurs de persistance restent à leurs frontières documentées.
- Exceptions génériques (`DomainException`, `ApplicationException`, exceptions applicatives transverses et Value Objects partagés) restent dans `shared_kernel`. Les exceptions propres à Order Detection sont sous `domain/exceptions`; l'exception de conflit de planification, qui relève de l'application, est sous `application/exceptions`.
- Imports actualisés dans le container, l'application, l'infrastructure et les tests; les modèles Django restent enregistrés via `contexts.order_detection.models`.
- Ajout du test d'architecture qui impose ces chemins et vérifie les frontières entre contextes.
- Validation : architecture 4/4; tests unitaires Order Detection 43/43; intégration Django Order Detection 13/13; `manage.py check` sans problème; `makemigrations --check --dry-run` sans changement.
- CRM, initialement non migré au début de cette reprise, a été réorganisé et validé ci-dessous.

### CRM — structure terminée

- Domain rangé sous `entities/`, `value_objects/`, `services/`, `repositories/`, `exceptions/` et `events/`; les ports et exceptions applicatifs sont des packages sous `application/ports` et `application/exceptions`.
- Modèles Django déplacés sous `infrastructure/persistence`; leur enregistrement public reste dans `contexts.crm.models`.
- Les imports du container, de l'infrastructure et des tests CRM suivent les nouveaux chemins. Le comportement métier n'a pas été modifié.
- Validation : tests unitaires CRM 39/39; intégration Django CRM 19/19; architecture dynamique 4/4; `manage.py check` OK; aucune migration CRM manquante.
- Limite Git : l'index contenait déjà des modifications et renommages CRM antérieurs à cette tâche. Aucun commit CRM n'est créé afin de ne pas embarquer ces changements préexistants.

### Blocage documentaire avant Identity / Access Control

- Les sept bounded contexts sont maintenant sous `src/contexts`. CRM et Order Detection ont des modules fonctionnels réorganisés; Identity, Access Control et Rules Engine sont des squelettes déplacés de `shared_kernel`; Platform Connectors et Backup restent des squelettes sans modules métier à déplacer.
- Contradiction Identity : `docs/05-module-structure.md` et `docs/13-technology-decision-adr.md` listent un contexte Identity séparé; `docs/15-use-cases-catalog.md` groupe « Identity & Access »; aucune spécification `docs/0X-context-identity.md` n'existe.
- Contradiction Access Control : `docs/20-context-access-control.md` définit cinq contrats (`CreateRole`, `UpdateRolePermissions`, `AssignRoleToUser`, `RevokeRoleFromUser`, `CheckPermission`), mais `docs/15-use-cases-catalog.md` ne définit aucun Use Case Access Control et le marque bloqué.
- `docs/24-permissions-catalog.md` interdit d'ajouter des permissions sans route réellement protégée. Aucun module de présentation/API n'est présent actuellement; le catalogue reste donc vide conformément à sa règle.
- Les sept middlewares sont déjà implémentés et enregistrés; les tests globaux les couvrent. Le catalogue des permissions reste vide tant qu'aucune route ne déclare réellement `@requires_permission`.
- Suite après déplacements : `python3 manage.py test tests --settings=config.test_settings -v 1` passe 32/32; architecture 4/4; `manage.py check` OK; aucune migration manquante.
- Reprise requise après décision documentaire : préciser si Identity est un contexte distinct et ajouter son document de contexte; intégrer ou non les cinq contrats Access Control dans le catalogue Use Cases; ne créer les permissions qu'en même temps que leurs routes effectives. Reprendre ensuite Platform Connectors, Rules Engine et Backup dans l'ordre utilisateur.
- Les commits par contexte n'ont pas été créés : l'index et le worktree contiennent des modifications utilisateur antérieures, notamment des fonctionnalités CRM/migrations déjà indexées et les changements Order Detection. Un commit ciblé risquerait d'embarquer ces changements; isoler l'index avant de committer.

## 2026-09-27 - Prise de contexte
## Checklist des Use Cases — état initial au 2026-10-14

Statut « fait » signifie contrat, implémentation, docstring avec invariants, permission sur la route et test. Les implémentations partielles restent « à faire ».

### Identity
- [ ] à faire — `RegisterMerchantUseCase` (implémentation et route protégée à créer)
- [ ] à faire — `ChangeSubscriptionPlanUseCase` (implémentation et route protégée à créer)

### Access Control
- [ ] bloqué — aucun Use Case Access Control n'est défini dans `docs/15-use-cases-catalog.md`; contrats nécessaires avant implémentation.

### Platform Connectors
- [ ] à faire — `ConnectPlatformUseCase`
- [ ] à faire — `SyncMessagesUseCase`
- [ ] à faire — `HandleIncomingWebhookUseCase`
- [ ] à faire — `RefreshTokensUseCase`

### Rules Engine
- [ ] à faire — `EvaluateMessageUseCase`
- [ ] à faire — `UpdateRuleSetUseCase`
- [ ] à faire — `AdjustRuleWeightFromCorrectionUseCase`

### Backup
- [ ] à faire — `CreateSnapshotUseCase`
- [ ] à faire — `RestoreFromSnapshotUseCase`
- [ ] à faire — `CheckAccountHealthUseCase`
- [ ] à faire — `DeleteAllMerchantDataUseCase`

### Order Detection
- [ ] à faire — `DetectOrderUseCase` (logique et tests présents; route protégée et architecture à compléter)
- [ ] à faire — `UpdateOrderStatusUseCase` (logique et tests présents; route protégée et architecture à compléter)
- [ ] à faire — `GetDormantMoneyDashboardUseCase` (logique et tests présents; route protégée et architecture à compléter)
- [ ] à faire — `ScheduleReminderUseCase` (logique et tests présents; route protégée et architecture à compléter)
- [ ] à faire — `SendScheduledRemindersUseCase` (logique et tests présents; route protégée et architecture à compléter)
- [ ] à faire — `ValidateOrRejectDetectionUseCase` (logique et tests présents; route protégée et architecture à compléter)
- [ ] à faire — `ListPendingDetectionCandidatesUseCase` (logique et tests présents; route protégée et architecture à compléter)
- [ ] à faire — `ReassignContactReferencesFromContactMergedUseCase` (logique et tests présents; consumer et architecture à compléter)

### CRM
- [ ] à faire — `UpdateContactFromMessageUseCase` (logique et tests présents; consumer protégé et architecture à compléter)
- [ ] à faire — `UpdateContactFromOrderUseCase` (logique et tests présents; consumer protégé et architecture à compléter)
- [ ] à faire — `CreateSegmentUseCase` (logique et tests présents; route protégée et architecture à compléter)
- [ ] à faire — `GetSegmentMembersUseCase` (logique et tests présents; route protégée et architecture à compléter)
- [ ] à faire — `SendBulkMessageUseCase` (logique et tests présents; route protégée et architecture à compléter)
- [ ] à faire — `ProcessBulkMessageCampaignUseCase` (implémentation présente; test et consumer à vérifier)
- [ ] à faire — `DetectRelationshipAnomalyUseCase` (logique et tests présents; job et architecture à compléter)
- [ ] à faire — `MergeContactsUseCase` (logique et tests présents; route protégée et architecture à compléter)

### Avancement 2026-10-14
- Restructuration partielle par `git mv`: les Use Cases CRM et Order Detection sont dans `application/use_cases`; leurs adaptateurs sont répartis entre `persistence`, `messaging` et `adapters`; ports et DTO Order Detection sont séparés.
- Les sept middlewares sont déplacés sous `src/middleware`, implémentés et enregistrés dans l'ordre documentaire. Tests dédiés: 7 passent.
- Ajout du test d'architecture Clean Architecture/frontières de contexte: 3 passent.
- CRM multi-devises: `spendingByCurrency`, erreur `CURRENCY_REQUIRED`, zéro pour une devise absente; devise principale passée au calcul du score. Contrats et INV-CRM-08 alignés.
- Validations: 39 tests unitaires CRM et 43 Order Detection passent; intégrations Django CRM 19/19 et Order Detection 13/13; middleware 7/7; architecture 3/3; `manage.py test tests` 32/32; `manage.py check` sans problème; aucune migration manquante.
- La checklist garde « à faire » pour tous les Use Cases, car aucune route protégée/permission n'est encore en place et des contextes n'ont pas d'implémentation; Access Control est bloqué car aucun Use Case n'est défini au catalogue.
- Commit par contexte non effectué: les fichiers CRM/Order Detection déplacés contiennent aussi des changements préexistants non committés. Un commit les inclurait avec ces modifications utilisateur; demander une séparation/validation avant commit.
- Bloquants avant production: relay Outbox et publisher Redis restent des placeholders; manque de routes avec `@requires_permission`, d'implémentations sur les contextes identity/access_control/platform_connectors/rules_engine/backup, et tests PostgreSQL concurrents.

## 2026-09-27 - Prise de contexte

### Documents consultes

- `docs/18-product-vision-and-objectives.md` : vision, cible, MVP (sauvegarde, detection de commandes/paiements, CRM), contraintes de cout et d'adaptabilite.
- `docs/16-business-invariants-and-rules.md` : invariants consolides; source de verite en cas de divergence.
- `docs/13-technology-decision-adr.md` : Python/Django, monolithe modulaire, PostgreSQL unique avec schemas par contexte; Redis pour les evenements; Rust reporte apres le MVP et mesure de charge.
- `docs/01-architecture-overview.md` : Clean Architecture, couches domain/application/infrastructure/presentation; dependances dirigees vers le domaine; communications inter-contextes par ports ou evenements.
- `docs/05-module-structure.md` : organisation par bounded context, puis par couche; shared-kernel, contexts, platform, tests et README par app.
- `docs/17-documentation-standards.md` : docstrings explicites, reference des invariants, README de chaque app et en-tetes pour les modules d'infrastructure.
- `.github/copilot-instructions.md` : lu integralement apres confirmation du proprietaire; injection par dependances, contrats documentes avant implementation, invariants testes, outbox transactionnelle, idempotence, stack Django/PostgreSQL et traitement d'une seule tache jusqu'a completion.
- `gabaris_a_repeter_pour_chaque_usecase.txt` : gabarit de demande pour `DetectOrderUseCase`, avec references aux contrats et invariants OD-01 a OD-04, a l'outbox et aux dependances injectees.
- `github/copilot-instructions.md` : fichier distinct present dans le workspace, vide lors de sa verification.

### Points de vigilance

- La premiere verification des fichiers caches n'a pas resolu `.github/copilot-instructions.md`; apres que le proprietaire a indique qu'il etait deja present, le chemin a ete ouvert et lu integralement. Utiliser ce fichier comme instructions Copilot faisant foi.
- Le dossier courant ne contient pas de metadonnees Git (`git status` indique que ce n'est pas un depot Git).
- Invariants retenus comme critiques pour la premiere synthese : consentement explicite avant sauvegarde de donnees clients (INV-BK-03), seuil de confiance et validation manuelle en dessous (INV-OD-04), agregation de montants dans une devise homogene via `Money` (INV-OD-05).

### Etat des changements

- Squelette Django cree, sans logique metier : apps Rules Engine, Identity, Access Control, Platform Connectors, Backup, Order Detection et CRM.
- Chaque app possede les couches `domain`, `application`, `infrastructure`, `presentation`, les migrations, un `AppConfig` et un README local. Les Value Objects/identifiants communs sont sous `src/shared_kernel`.
- La couche transverse est nommee `piedlens_platform` pour eviter de masquer le module standard Python `platform`.
- Ajoutes : projet `config/`, `manage.py`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.gitignore`, `.env.example`, README racine et dossiers de tests unitaires/integration/E2E.
- Compose demarre Django, PostgreSQL et Redis. PostgreSQL exige `POSTGRES_PASSWORD` dans `.env`; aucun secret n'est commite. Les services de donnees ne publient pas de port hote.
- Le journal n'est plus le seul fichier ajoute; il reste le registre des evolutions a maintenir a chaque etape importante.

### Validation

- `docker compose config --quiet` reussit avec une valeur temporaire de `POSTGRES_PASSWORD` fournie uniquement dans l'environnement.
- Analyse syntaxique AST : les 23 fichiers Python passent.
- `docker compose run --build --rm django python manage.py check` n'a pas pu terminer : le daemon Docker echoue lors de la creation d'un conteneur car `/mnt/Storage/docker-data/containers` est absent. Ce blocage est propre a l'hote; aucune erreur Django n'a encore ete observee.
- Le dossier de travail n'est pas un depot Git, donc `git status`/diff n'est pas disponible.

### Prochaine etape

Commencer l'implementation fonctionnelle un Use Case a la fois, en suivant son contrat dans `docs/15-use-cases-catalog.md`, les invariants et les standards de documentation/tests. Le gabarit du projet cible `DetectOrderUseCase` comme prochaine implementation. Avant de poursuivre le controle Docker, faire corriger la configuration du daemon ou son chemin de stockage.

## 2026-09-27 - Revue du contrat DetectOrderUseCase

- Documents relus avant implementation : `docs/02-domain-model.md`, `docs/08-context-rules-engine.md`, `docs/11-context-order-detection.md`, `docs/14-event-driven-architecture.md`, `docs/22-error-handling-and-exceptions.md` et `docs/23-shared-kernel-value-objects.md`.
- Blocage fonctionnel a clarifier avant de coder : `docs/15-use-cases-catalog.md` fait retourner `{ orderId, status: "pending_payment"|"needs_manual_validation" }`, mais `OrderStatus` ne contient pas `needs_manual_validation` et INV-OD-04 interdit qu'une detection sous le seuil devienne une commande automatique. `docs/11-context-order-detection.md` indique qu'elle va dans une file de validation manuelle sans definir l'agregat, l'identifiant ou le repository de cette file.
- Recommandation a valider : modeliser la detection sous le seuil comme une entite/agregat de validation distincte et ne creer aucun `Order` avant approbation; mettre a jour le contrat du catalogue (notamment l'identifiant retourne) avant implementation.
- Etat : implementation de `DetectOrderUseCase` en attente de decision du proprietaire; aucun code fonctionnel n'a ete ajoute.

## 2026-09-27 - Implementation de DetectOrderUseCase

### Contrats/documentation alignes

- `docs/16-business-invariants-and-rules.md` definit INV-OD-07 : DetectionCandidate distinct sous le seuil, decision unique, Order cree seulement apres validation manuelle.
- `docs/02-domain-model.md` documente DetectionCandidate et le dernier timestamp de signal montant sur Order.
- `docs/15-use-cases-catalog.md` specifie les resultats `order_created`, `candidate_created` ou `ignored`, la correlation possible vers une commande existante, et le timestamp source requis pour proteger INV-OD-03.
- `docs/11-context-order-detection.md` precise le traitement hors ordre des messages.

### Implementation ajoutee

- Shared kernel : `Money`, `ConfidenceScore` et exceptions de domaine partagees.
- Order Detection domain : `OrderStatus`, `Order`, `DetectionCandidate`, exceptions, `IOrderRepository` et `IDetectionCandidateRepository`.
- Application : `DetectOrderUseCase`, `EvaluationResult`, configuration injectee, resultats typables, evenements `OrderDetected`/`DetectionCandidateCreated`, port d'outbox et UnitOfWork.
- Score sous le seuil : candidat, sans creation d'Order (INV-OD-04/07); score au seuil : creation/correlation d'Order.

### Validation

- `PYTHONPATH=src python3 -m unittest tests.unit.order_detection.test_detect_order_use_case -v` : 7 tests passent.
- Couverture : transition invalide, statuts non modifiables directement, candidat a decision unique, seuils, correlation temporelle et montant conserve par timestamp source.
- Diagnostics VS Code sur le contexte, le shared kernel et le test : aucune erreur.
- Docker n'a pas pu executer `manage.py check`, le daemon echouant sur son chemin de stockage absent; les tests unitaires purs passent.

## 2026-09-27 - ValidateOrRejectDetectionUseCase

### Decision transactionnelle

- Le contrat initial faisait modifier DetectionCandidate et creer Order dans la meme operation, ce qui violait INV-TR-01.
- La decision ne modifie maintenant que DetectionCandidate et publie ses evenements dans son outbox; `CreateOrderFromPromotedDetectionUseCase` cree Order dans une transaction distincte.

### Implementation et tests

- Ajoute `ValidateOrRejectDetectionUseCase` avec validation, controle merchant scope et feedback Rules Engine par `matchedRuleIds`.
- `DetectionCandidate` garde la reference des regles declenchees; erreurs applicatives partagees pour valeur invalide/ressource absente.
- Suite Order Detection au moment de cette etape : 12 tests passent; analyse AST : 22 fichiers valides.
- Aucun changement CRM ne fait partie de cette etape.
- `PYTHONPATH=src python3 -m unittest discover -s tests/unit/order_detection -p 'test_*.py' -v` : 12 tests passent.
- Analyse AST : 22 fichiers Python valides; diagnostics VS Code sur le contexte, le shared kernel, les tests et le journal : aucune erreur.
- Le test d'integration Django/Docker n'a pas ete relance, car le daemon echouait deja sur son chemin de stockage manquant; validation pure du domaine/application reussie.

## 2026-09-27 - CreateOrderFromPromotedDetectionUseCase

### Implementation

- Ajoute le consommateur `CreateOrderFromPromotedDetectionUseCase` : cree un Order `pending_payment` depuis l'evenement immuable `DetectionCandidatePromoted`, sans relire ni modifier le candidat.
- La transaction consomme `processed_events(eventId, consumerName)`, verrouille la creation par `candidateId`, sauvegarde l'Order, ajoute `OrderDetected` a l'outbox et marque l'evenement traite dans le meme unit of work.
- `Order.source_candidate_id` fournit une deuxieme protection metier contre les redeliveries republiees avec un nouvel eventId; la contrainte UNIQUE est maintenant appliquee par la migration Django `0001_initial`.
- Le catalogue, le modele de domaine, le contexte et le README precisent l'enveloppe contenant eventId/occurredAt et les contraintes d'idempotence.

### Tests et validation

- Trois tests dedies passent : creation atomique attendue, rejeu du meme event sans doublon, nouvel eventId pour le meme candidat sans second Order.
- Suite complete : `PYTHONPATH=src python3 -m unittest discover -s tests/unit/order_detection -p 'test_*.py' -v` : 15 tests passent.
- Analyse syntaxique : 25 fichiers Python valides; diagnostics VS Code sur les documents, modules, tests et journal : aucune erreur.
- Prochaine tache dans l'ordre du catalogue : `UpdateOrderStatusUseCase`; consulter son contrat et les invariants avant implementation.

## 2026-09-27 - Transactions ACID concretes

- Constat de revue : avant ce travail, les Use Cases ne possedaient que des Protocols UnitOfWork et les tests des faux context managers; il n'y avait pas de `transaction.atomic()`, de repository ORM ni de tables outbox/processed enregistrees.
- Ajoutes modeles et migration Django pour Order, DetectionCandidate, outbox_events, processed_events et verrou de creation candidat.
- `DjangoOrderDetectionUnitOfWork` ouvre `transaction.atomic()` sur la connexion par defaut; repositories, outbox et marqueurs utilises dans le meme bloc partagent cette connexion.
- Ajoutes les adaptateurs Django et le composition root `piedlens_platform.di.container.ApplicationContainer` pour l'injection; les Use Cases ne construisent pas d'infrastructure.
- Ajoute `config.test_settings` en SQLite memoire pour les tests Django locaux.
- Tests d'integration finaux : `python3 manage.py test tests.integration.order_detection --settings=config.test_settings -v 2` : 4/4 passent (commit agregat+outbox+processed, rollback global, idempotence redelivery, rollback de decision candidat/outbox).
- Tests unitaires Order Detection : 15/15 passent.
- `python3 manage.py makemigrations order_detection --check --dry-run --settings=config.test_settings` : aucune migration manquante.
- Systeme check Django pendant les tests : aucun probleme.
- Limites : Django local 4.2.11 contre 5.2+ dans requirements; SQLite ne teste pas les verrous Postgres; les tables `order_detection_*` restent dans le schema public/par defaut, pas encore dans le schema natif `order_detection` demande par l'ADR.

## 2026-09-27 - UpdateOrderStatusUseCase

- Contrat `docs/15-use-cases-catalog.md` relu; les erreurs explicites sont INVALID_STATUS, INVALID_ACTOR, ORDER_NOT_FOUND et INVALID_ORDER_TRANSITION.
- Ajoute `OrderStatusChanged`, le port `find_by_id`, le port d'horloge et le verrou `lock_order` au UnitOfWork.
- `UpdateOrderStatusUseCase` charge l'Order verrouille, delegue la validation a `Order.change_status()` (INV-OD-01), puis persiste l'Order et son evenement d'outbox dans la meme transaction (INV-TR-01/02).
- Le composition root injecte `SystemClock`, repository, UnitOfWork et outbox; aucun adaptateur infra n'est instancie dans le Use Case.
- Suite Order Detection : `PYTHONPATH=src python3 -m unittest discover -s tests/unit/order_detection -p 'test_*.py' -v` : 19 tests passent.
- Suite d'integration : `python3 manage.py test tests.integration.order_detection --settings=config.test_settings -v 2` : 5 tests passent, dont le changement de statut et l'outbox via ORM.
- `python3 manage.py makemigrations order_detection --check --dry-run --settings=config.test_settings` : aucune migration manquante; Django system check : aucun probleme.
- Prochaine tache dans l'ordre du catalogue : `GetDormantMoneyDashboardUseCase`; lire contrat/invariants puis implementer calcul strictement par devise via `Money.add()`.

## 2026-09-27 - GetDormantMoneyDashboardUseCase

### Contrat clarifie et implementation

- Le contrat precedent `totalDormantAmount: Money` ne pouvait pas representer plusieurs devises sans conversion interdite/non definie. Il retourne maintenant `totalsByCurrency: Money[]`, un total distinct par devise (INV-OD-05).
- Filtre les Orders du merchant en `pending_payment` ou `paid_not_delivered`, plus anciennes que `olderThanHours` (defaut 24); annulees/livrees, autres merchants et commandes recentes sont exclues.
- Tri ORM : plus ancienne d'abord, puis montant decroissant. `olderThanHours` non entier, booleen, nul ou negatif est rejete comme `INVALID_OLDER_THAN_HOURS`.
- Implementes port `find_dormant`, requete du `DjangoOrderRepository`, summaries/resultats immuables, agregation avec `Money.add()` par devise et wiring via `ApplicationContainer`.
- `docs/15-use-cases-catalog.md` et `docs/11-context-order-detection.md` ont ete ajustes pour le contrat multi-devise et l'ordre de tri.

### Validation

- Tests unitaires cibles : 3 passent (groupement XOF/USD, statut ferme exclu, seuil par defaut et seuil invalide).
- Test d'integration cible avec ORM : passe, couvre anciennete, merchant scope, statut, tri et totaux par devise.
- Suite complète Order Detection : `PYTHONPATH=src python3 -m unittest discover -s tests/unit/order_detection -p 'test_*.py' -v` : 22 tests passent.
- Suite d'integration Django : `python3 manage.py test tests.integration.order_detection --settings=config.test_settings -v 2` : 6 tests passent.
- `makemigrations --check --dry-run` : aucune migration manquante; analyse AST : 43 fichiers Python valides; aucun diagnostic VS Code sur les fichiers contrôlés.
- Prochaine tâche dans l'ordre du catalogue : `ScheduleReminderUseCase`; vérifier la règle anti-doublon INV-OD-06 et les règles de planification avant implémentation.

## 2026-09-27 - ScheduleReminderUseCase

### Contrat et architecture

- Migration `0002_reminderrecord_and_more` cree la table, l'index de traitement et l'unicite conditionnelle.
- Le composition root injecte le provider requis, l'horloge, le repository, l'outbox et le UnitOfWork.
- Contrats catalogue/domain/context mis a jour; correction d'un doublon preexistant de `INVALID_OLDER_THAN_HOURS` dans le catalogue.

### Validation

- Tests unitaires cibles : 6 passent.
- Test d'integration ORM anti-doublon + outbox : passe.
- Suite complete Order Detection : `PYTHONPATH=src python3 -m unittest discover -s tests/unit/order_detection -p 'test_*.py' -v` : 28 tests passent.
- Suite d'integration Django : `python3 manage.py test tests.integration.order_detection --settings=config.test_settings -v 2` : 7 tests passent.
- `makemigrations --check --dry-run` : aucune migration manquante; analyse syntaxique AST : 51 fichiers Python valides; aucun diagnostic VS Code sur les fichiers documentaires controles.
- Prochaine tache dans l'ordre du catalogue : `SendScheduledRemindersUseCase`; examiner l'idempotence du consumer, le contrat `IMessageSender` et les limites du plan avant implementation.

## 2026-09-27 - SendScheduledRemindersUseCase

### Contrat et implementation

- Contrat etendu : resultat `sentCount`, `proposedCount`, `failedCount`; policy injectee distingue proposition manuelle Starter et envoi Pro/Agency.
- Ajoutes ports de rendu de message configure, policy plan, livraison et retry; l'envoi externe utilise `Reminder.id` comme cle d'idempotence.
- Worker avec claim batch transactionnel, lease/token, recouvrement apres expiration, verification d'appartenance avant finalisation, et annulation si l'Order n'est plus dans l'etat attendu.
- Starter produit `ReminderProposed` sans appel externe; succes automatic produit `ReminderSent`; echec incremente les tentatives et emet `ReminderDeliveryFailed` avec retry date. Marqueurs `processed_events` ecrits avec les evenements et transitions terminales dans la transaction.
- L'appel externe est hors transaction DB; la garantie anti-double envoi requiert que l'adaptateur de livraison respecte/dedupplique la cle idempotente.
- Migration `0003` ajoute leaseUntil, leaseToken, attemptCount, nextAttemptAt et etend l'unicite aux rappels `scheduled` ou `processing`.

### Validation en cours

- Tests unitaires cibles : 6 passent (auto, manuel, retry, Order obsolete, lease recupere, reponse apres expiration ignoree).
- Tests d'integration ORM cibles : claim/sent/outbox et reclaim lease expire passent.
- Tests unitaires complets : `PYTHONPATH=src python3 -m unittest discover -s tests/unit/order_detection -p 'test_*.py' -v` : 34 tests passent.
- Tests d'integration Django : `python3 manage.py test tests.integration.order_detection --settings=config.test_settings -v 2` : 9 tests passent, y compris envoi + outbox + processed marker et récupération lease.
- `python3 manage.py makemigrations order_detection --check --dry-run --settings=config.test_settings` : aucune migration manquante; analyse AST : 55 fichiers Python valides; diagnostics VS Code des documents contrôlés : aucune erreur.
- Limite de validation : SQLite ne garantit pas le comportement de concurrence Postgres pour `skip_locked/select_for_update`; ajouter un test concurrent PostgreSQL en CI. L'adaptateur réel de livraison doit dédupliquer les retries/crash avec `Reminder.id` avant mise en production.
- Prochaine tâche dans l'ordre du catalogue : `ListPendingDetectionCandidatesUseCase`.

## 2026-09-27 - ListPendingDetectionCandidatesUseCase

### Contrat et implementation

- Contrat precise : page par defaut 1, pageSize 50/max 100, seulement `pending_review` du merchant demande, tri anciennete puis UUID stable, total avant pagination; erreurs pour parametres invalides.
- Repository Django ajoute count + slicing et projection de l'aggregate; Use Case retourne des `DetectionCandidateSummary` sans muter de domaine.
- Composition root cable le Use Case en lecture seule.

### Validation en cours

- Tests unitaires complets : `PYTHONPATH=src python3 -m unittest discover -s tests/unit/order_detection -p 'test_*.py' -v` : 37 tests passent.
- Tests d'integration Django : `python3 manage.py test tests.integration.order_detection --settings=config.test_settings -v 2` : 10 tests passent.
- `python3 manage.py makemigrations order_detection --check --dry-run --settings=config.test_settings` : aucune migration manquante; analyse AST : 57 fichiers Python valides; aucun diagnostic VS Code sur les documents controles.
- Prochaine tache dans l'ordre global du catalogue : `UpdateContactFromMessageUseCase`, contexte CRM; relire d'abord `docs/12-context-crm.md`, les invariants CRM et le contrat associe.

## 2026-09-27 - UpdateContactFromMessageUseCase (CRM)

### Contrat clarifie

- L'enveloppe `MessageReceived` inclut `eventId` pour l'idempotence du consumer INV-TR-03.
- Cle de Contact : `(merchantId, platformConnectionId, externalIdentifier)`; les connexions distinctes ne sont pas fusionnees automatiquement.
- `totalSpent` initial est un `Money` zero dont la devise vient de `IContactDefaultsProvider`, sans appel direct vers Identity.
- Les messages anciens ne font pas reculer `lastInteractionAt` ni le displayName; les totaux d'achat ne sont pas touches (INV-CRM-01/04).

### Implementation

- Ajoutes Aggregate Root Contact, Value Object CRM `LoyaltyScore`, repository port, defaults provider, ports unit-of-work/idempotence et `UpdateContactFromMessageUseCase`.
- Models Django CRM : table Contact avec unicite composite et ledger `crm_processed_events`; adapters ORM et `DjangoCRMUnitOfWork` partagent une transaction.
- `get_or_create` avec contrainte SQL gere les courses de creation; les contacts existants sont relus sous `select_for_update()` avant mutation.
- Composition root injecte les adapters et exige un provider de defaults.
- Migration CRM `0001_initial` generee.

## 2026-09-27 - UpdateContactFromOrderUseCase (CRM)

### Contrat et implementation

- L'evenement OrderStatusChanged transporte maintenant `detectedAmount: Money`; le consumer CRM ne lit jamais les tables/repositories Order Detection.
- `Contact.totalSpentByCurrency` remplace le Money unique afin de respecter INV-OD-05 sans conversion implicite. Migration CRM `0002` convertit les anciens montants/devises vers une map JSON avant de retirer les colonnes simples; le rollback refuse explicitement les contacts multi-devises.
- Consumer idempotent par eventId, transaction CRM avec Contact + processed_events, verrou Contact, mutation uniquement pour `paid_and_delivered`.
- Chaque somme utilise `Money.add()` par devise; `orderCount` s'incremente dans le meme chemin INV-CRM-04.
- `ILoyaltyScoreCalculator` est injecte; aucune formule metier non spécifiée n'est improvisée. Le composition root exige ce service externe.

### Validation en cours

- Tests unitaires ciblés et intégration de migration/rollback à exécuter dans la validation finale ci-dessous.

### Validation

- Tests unitaires CRM : `PYTHONPATH=src python3 -m unittest discover -s tests/unit/crm -p 'test_*.py' -v` : 6 tests passent.
- Tests d'integration globaux : `python3 manage.py test tests.integration --settings=config.test_settings -v 2` : 13 tests passent.
- `python3 manage.py makemigrations --check --dry-run --settings=config.test_settings` : aucune migration manquante; analyse AST : 99 fichiers Python valides; diagnostics VS Code des documents controles : aucune erreur.
- Prochaine tâche CRM dans l'ordre : `UpdateContactFromOrderUseCase`; vérifier INV-CRM-04, corrélation par contactId et idempotence de l'événement `OrderStatusChanged`.

## 2026-09-28 - CRM segments et envoi massif

### Contexte et discipline

- Reprise stricte du projet depuis `evolution.md`, sans saut d’étape, en respectant la priorité documentaire : `docs/12-context-crm.md`, `docs/15-use-cases-catalog.md`, `docs/02-domain-model.md` puis tests ciblés avant validation.
- Les use cases déjà implémentés et validés servent de référence de structure transactionnelle et de Clean Architecture : `UpdateContactFromMessageUseCase`, `UpdateContactFromOrderUseCase`, puis les nouveaux cas CRM segmentaires.
- Les règles de production sont respectées : injection de dépendances, use case unique, transactions ACID au niveau UnitOfWork, idempotence sur les événements, pas de logique métier dans des contrôleurs ou webhooks, et validation de contrats avant code.

### Implémentation ajoutée

- `CreateSegmentUseCase` : validation des champs et opérateurs autorisés, création d’un `CRMSegment` avec `SegmentRule` et sauvegarde via le port repository.
- `GetSegmentMembersUseCase` : evaluation dynamique de l’appartenance via `SegmentMembershipCalculator`, projection du résultat en résumé paginé pour les contacts matchant la règle.
- `SendBulkMessageUseCase` : calcul dynamique des membres du segment, respect du `rate_limiter`, envoi.annoté par canal, retour de status de traitement avec nombre de destinataires.
- Domain CRM étendu : `CRMSegment`, `SegmentRule`, `SegmentMembershipCalculator`, `ISegmentRepository`.

### Tests validés

- `PYTHONPATH=src python3 -m unittest tests.unit.crm.test_create_segment_use_case -v` : 3 tests passent.
- `PYTHONPATH=src python3 -m unittest tests.unit.crm.test_get_segment_members_use_case -v` : 1 test passe.
- `PYTHONPATH=src python3 -m unittest tests.unit.crm.test_send_bulk_message_use_case -v` : 1 test passe.
- `PYTHONPATH=src python3 -m unittest discover -s tests/unit/crm -p 'test_*.py' -v` : 15 tests passent.

### Point de vigilance

- L’environnement PostgreSQL/Docker n’est pas un “run normal” pour les tests de validation locale ; la config de test SQLite du projet reste la bonne référence pour exécuter les suites unitaires locales sans faux négatifs.
- Le workflow de projet impose que chaque tâche soit terminée et validée avant d’enchaîner sur la suivante.

### Prochaine étape

- Poursuivre strictement le catalogue CRM avec le prochain use case documenté après `SendBulkMessageUseCase`, en appliquant la même méthode de validation : contrat doc → test ciblé → implémentation → test.
- Continuer à mettre à jour ce journal à chaque étape importante du projet.

## 2026-09-28 - DetectRelationshipAnomalyUseCase

### Contrat et comportement

- Le use case CRM `DetectRelationshipAnomalyUseCase` est le prochain élément documenté après les segments et l’envoi massif.
- Le contrat attendu est un scan des contacts d’un merchant et un signal `inactive_for_too_long` lorsqu’un contact dont l’activité est déjà établie reste inactif trop longtemps.
- La logique est strictement de lecture : le use case ne modifie pas l’agrégat `Contact`; il renvoie la liste des anomalies détectées pour publication ou notification downstream.

### Implémentation ajoutée

- Ajout du use case `detect_relationship_anomaly_use_case.py` dans la couche application CRM.
- Vérification de la règle d’inactivité en calculant l’écart en jours entre `last_interaction_at` et maintenant.
- Les contacts sans historique d’achat ou trop récents sont ignorés ; l’anomalie n’est détectée que sur les profils actifs historiquement.

### Test validé

- `PYTHONPATH=src python3 -m unittest tests.unit.crm.test_detect_relationship_anomaly_use_case -v` : 2 tests passent.

### Validation de discipline

- Le workflow a été respecté : contrat documentaire, test ciblé, implémentation minimale, validation de comportement, puis mise à jour du journal.
- La progression reste cohérente avec le catalogue CRM et les invariants de contexte.

### Revue ACID et statut réel

- `DetectRelationshipAnomalyUseCase` ne modifie actuellement aucun agrégat : sa lecture seule ne nécessite pas de transaction ACID.
- Le catalogue et `docs/12-context-crm.md` exigent `RelationshipAnomalyDetected` par anomalie; sa persistance passe par une Outbox CRM dans la transaction ACID de la notification.
- Les documents CRM mis à jour définissent désormais l'historique suffisant, la médiane des intervalles d'achat, le multiplicateur et le plancher d'inactivité. Les trois paramètres proviennent de la configuration.
- Le seuil fixe de 30 jours et l'implémentation provisoire fondée sur `last_interaction_at` ont été retirés; les tests de cette règle erronée ont également été supprimés.
- Le use case complet reste à implémenter dans la tâche D, après l'historique d'achats CRM (B) et l'enregistrement transactionnel des alertes (C).
- Validation après retrait : `PYTHONPATH=src python3 -m unittest discover -s tests/unit/crm -p 'test_*.py' -v` : 15 tests passent; recherche ciblée du seuil et du comportement provisoire dans le code/tests CRM : aucune occurrence; diagnostics VS Code : aucune erreur.

## 2026-09-28 - Tâche A : Outbox CRM transactionnelle

### Implémentation

- Ajout de `crm_outbox_events` avec enveloppe versionnée, payload JSON, état de publication et index de relay.
- Ajout du port `ICRMOutbox` et de l’adaptateur `DjangoCRMOutbox`; l’adaptateur écrit uniquement en base et utilise la connexion active du `DjangoCRMUnitOfWork`.
- Ajout de la migration `0003_outboxeventrecord` et mise à jour du README CRM.
- Les écritures métier, les marqueurs CRM existants et l’Outbox partagent le `transaction.atomic()` du UnitOfWork; aucune publication Redis directe n’est ajoutée.

### Validation

- `python3 manage.py test tests.integration.crm.test_transactional_outbox --settings=config.test_settings -v 2` : 2 tests passent (commit atomique et rollback atomique).
- `PYTHONPATH=src python3 -m unittest discover -s tests/unit/crm -p 'test_*.py' -v` : 17 tests passent.
- `python3 manage.py makemigrations crm --check --dry-run --settings=config.test_settings` : aucune migration manquante.
- Suite intégration CRM complète : 7 tests passent, 1 échoue sur une assertion existante du rejeu d’événement (`replay.applied` attendu `True`, alors que le consumer idempotent retourne `False`). Les deux tests Outbox passent dans cette suite; cet échec n’est pas modifié dans la tâche A.

### Prochaine étape

- Tâche A terminée. La tâche B est consignée ci-dessous.

## 2026-09-28 - Tâche B : historique d’achats CRM

### Implémentation

- `Contact` possède maintenant un historique CRM d’entrées immuables `{order_id, purchased_at}`; la date est `updatedAt` de l’événement `OrderStatusChanged` lorsque le statut est `paid_and_delivered`.
- `Contact.record_paid_order()` déduplique par `order_id`, afin qu’une republication sous un nouvel `eventId` ne modifie ni le total, ni `order_count`, ni l’historique une deuxième fois.
- Le consumer existant garde son contrôle `(eventId, crm-order-consumer)`, son verrou Contact et sa transaction unique pour l’agrégat et le marqueur `processed_events` (INV-CRM-04/INV-TR-03).
- Le mapping ORM persiste et recharge les dates dans `crm_contacts.purchase_history`; migration CRM `0004_contactrecord_purchase_history` ajoutée. Aucune table Order Detection n’est lue.
- Le catalogue, le modèle de domaine et le document du contexte précisent le payload de l’événement, la date retenue et la limite de rétroactivité. Les dates antérieures au déploiement ne sont pas reconstruites, conformément à INV-TR-04.
- L’assertion d’intégration `replay.applied` a été corrigée pour attendre `False`, conforme au comportement idempotent du consumer.

### Validation

- Tests unitaires ciblés du consumer : 5 passent, dont la date source, la non-duplication par `order_id` et l’idempotence par `eventId`.
- `PYTHONPATH=src python3 -m unittest discover -s tests/unit/crm -p 'test_*.py' -v` : 16 tests passent.
- `python3 manage.py test tests.integration.crm.test_update_contact_from_order --settings=config.test_settings -v 2` : 4 tests passent.
- `python3 manage.py test tests.integration.crm --settings=config.test_settings -v 2` : 9 tests passent.
- `python3 manage.py makemigrations crm --check --dry-run --settings=config.test_settings` : aucune migration manquante.
- Diagnostics VS Code sur le domaine, l’application, l’infrastructure, les tests et les documents modifiés : aucune erreur.

### Prochaine étape

- B est terminé. Les tâches C et D sont consignées ci-dessous.

## 2026-09-28 - Tâches C et D : alertes et détection d’anomalie CRM

### Notification et Outbox (C)

- Ajout de `RelationshipAnomalyNotification` et de son record Django; unicité SQL sur `(contact_id, last_purchase_order_id)` pour n’émettre qu’une alerte par période de silence, y compris sous exécutions concurrentes.
- Ajout de l’événement `RelationshipAnomalyDetected` et du repository `save_if_absent`; notification et événement Outbox sont écrits dans le même `DjangoCRMUnitOfWork`.
- Tests d’intégration : doublon bloqué dans une période, nouvel achat ouvrant une nouvelle période, et rollback conjoint notification/Outbox.

### Détection configurée (D)

- Ajout du `RelationshipAnomalyPolicy` validé, du service domaine pur qui calcule la médiane des intervalles d’achats consécutifs et applique le multiplicateur strict et le plancher minimum.
- `DetectRelationshipAnomalyUseCase` utilise exclusivement l’historique d’achat CRM, relit chaque Contact sous verrou dans sa transaction, et enregistre seulement les nouvelles alertes avec l’événement Outbox.
- Les defaults viennent des settings Django (`min_purchases=3`, `anomaly_multiplier=2.0`, `min_inactivity_days=7`); l’adaptateur accepte les overrides par merchant. Aucune de ces valeurs métier n’est définie dans le domaine.
- Exceptions de policy documentées selon `docs/22-error-handling-and-exceptions.md`; catalogue, contexte et README CRM mis à jour; wiring ajouté au composition root.

### Validation

- Tests unitaires CRM : `PYTHONPATH=src python3 -m unittest discover -s tests/unit/crm -p 'test_*.py' -v` : 21 tests passent.
- Tests d’intégration CRM : `python3 manage.py test tests.integration.crm --settings=config.test_settings -v 2` : 14 tests passent.
- Couverture : historique insuffisant, multiplicateur, plancher d’inactivité, policy invalide, pas de doublon, nouvel achat ouvrant une nouvelle période, overrides merchant, transactions Outbox et migration ORM.
- `python3 manage.py makemigrations crm --check --dry-run --settings=config.test_settings` : aucune migration manquante.

### Prochaine étape CRM

- `MergeContactsUseCase` est le prochain cas CRM restant au catalogue; son contrat et la frontière d’agrégat devront être relus avant implémentation.
- Les segments et l’envoi massif gardent des écarts de persistance/wiring et de contrat; les intégrations réelles aux plateformes externes restent hors périmètre tant que leurs adapters documentés ne sont pas implémentés et testés.

## 2026-09-28 - Décision de fusion et blocage Outbox production

- Décision propriétaire : INV-TR-01 est conservé sans exception. `MergeContactsUseCase` se déroule en deux temps/transactions : tombstone du doublon + Outbox `ContactMerged`, puis absorption CRM sur le principal par consumer idempotent. Order Detection réattribue chaque Order et DetectionCandidate dans sa propre transaction, avec reprise idempotente.
- Les contrats et invariants de `docs/12-context-crm.md`, `docs/15-use-cases-catalog.md`, `docs/16-business-invariants-and-rules.md` et `docs/14-event-driven-architecture.md` sont mis à jour pour le tombstone `Merged`, la redirection, le payload snapshot et la cohérence éventuelle.
- **BLOQUANT AVANT MISE EN PRODUCTION** : `OutboxRelayWorker` et `RedisStreamEventPublisher` sont encore des placeholders. Les événements présents dans les tables Outbox ne sont donc pas livrés à Redis; aucun flux inter-contextes qui en dépend ne peut être considéré opérationnel tant que relay, publication, reprise/ack et tests bout en bout ne sont pas implémentés.
- Aucun code de fusion n'est implémenté dans cette étape documentaire. Prochaine action : tests puis implémentation CRM temps 1, CRM temps 2, puis Order Detection consumer, chacun séparément et conformément aux nouveaux contrats.

## 2026-09-28 - Fusion CRM temps 1 et temps 2

### Décision métier appliquée

- Le propriétaire a explicitement élargi INV-CRM-04 : seuls `OrderStatusChanged` (`paid_and_delivered`) et `ContactMerged` (absorption du snapshot) peuvent modifier `totalSpent` et `orderCount`.
- `docs/16-business-invariants-and-rules.md`, `docs/12-context-crm.md` et `docs/15-use-cases-catalog.md` décrivent désormais cette règle et son traitement idempotent.

### Implémentation

- `Contact.absorb_merged_contact()` additionne les montants par devise via `Money.add()`, ajoute le `orderCount` du snapshot, unit l'historique et les tags.
- Ajout de `ConsumeContactMergedUseCase` : verrouille et modifie uniquement le Contact principal, consomme `processed_events` dans le même `DjangoCRMUnitOfWork`, et rejoue un événement déjà traité sans nouvelle addition.
- Le composition root expose le consumer; le README CRM reflète MergeContactsUseCase et le consumer comme implémentés.
- Le test d'intégration CRM vérifie l'addition multi-devise, le compteur et le rejeu idempotent. Aucun changement n'a été apporté au contexte Order Detection dans cette tâche.

### Validation

- Test unitaire fusion ciblé : 6/6 passent.
- Tests unitaires CRM : 28/28 passent.
- Tests d'intégration CRM sous SQLite : 17/17 passent; le system check Django ne signale aucun problème.
- Tests unitaires Order Detection : 37/37 passent.
- Tests d'intégration Order Detection sous SQLite : 10/10 passent.
- `python3 manage.py makemigrations --check --dry-run --settings=config.test_settings` : aucune migration manquante.
- Le relay Outbox reste un placeholder bloquant avant livraison réelle des événements à Redis. Le consumer Order Detection de `ContactMerged` (réattribution des Orders et DetectionCandidates) reste à implémenter dans une tâche distincte.

### Prochaine étape en attente

- Après validation du propriétaire sur ce jalon, poursuivre par le consumer CRM `ContactMerged` si le wiring de production le requiert, puis traiter séparément le consumer Order Detection selon le contrat catalogue. Ne pas considérer les événements comme distribués tant que le relay Outbox n'est pas implémenté et testé.

## 2026-09-28 - Consumer Order Detection de ContactMerged

### Implémentation

- Ajout de `ReassignContactReferencesFromContactMergedUseCase` et de son DTO local Order Detection; le consumer ignore le snapshot CRM et ne dépend d'aucune classe du contexte CRM.
- Ajout des méthodes de recherche d'IDs et de chargement verrouillé dans les ports et repositories Order Detection. Les agrégats `Order` et `DetectionCandidate` exposent leur propre opération de réattribution.
- Chaque agrégat est revalidé et modifié dans une transaction distincte. Le marqueur `order-detection-contact-merge-consumer` n'est écrit qu'après le balayage des Orders et des DetectionCandidates.
- Les références déjà réattribuées sont ignorées lors d'une reprise. `DjangoProcessedEventRepository.mark_processed()` utilise désormais `get_or_create()` pour rendre l'insertion du marqueur finale tolérante à une livraison concurrente.
- Le composition root, le README Order Detection, `docs/11-context-order-detection.md` et le contrat du catalogue documentent le consumer.

### Validation

- Tests unitaires Order Detection : 39/39 passent, dont filtrage des références, redelivery sans effet et reprise après échec partiel.
- Tests d'intégration ORM ciblés : 12/12 passent sous SQLite, dont le commit séparé de chaque agrégat et la reprise sans marqueur prématuré.
- `python3 manage.py makemigrations order_detection --check --dry-run --settings=config.test_settings` : aucune migration détectée.
- Diagnostics VS Code sur les modules, adapters, wiring et tests touchés : aucune erreur.
- SQLite ne valide pas la concurrence réelle PostgreSQL; le contrôle concurrent PostgreSQL CI reste requis. Aucun relay Redis n'a été ajouté.

### Prochaine étape en attente

- Attendre la validation du propriétaire avant d'entreprendre une autre tâche. La publication des événements `ContactMerged` n'est pas opérationnelle en bout en bout tant que le relay Outbox et son worker de consommation ne sont pas implémentés.