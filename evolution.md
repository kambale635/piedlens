# Journal d'evolution du projet

Ce fichier conserve les decisions, documents consultes, fichiers crees ou modifies et prochaines etapes afin de faciliter la reprise du projet.
Mettre a jour ce journal a chaque etape importante.

## 2026-10-23 - Phase 4 Billing : rapport de valeur et validation des routes

- Rapport mensuel de valeur ajouté : usages API du mois par merchant, pays/devise, estimation par tarif actif et signalement explicite des catégories non tarifées.
- Ajout de l'erreur `OUTBOUND_RATE_MISSING` avant réservation du quota, route protégée `GET /api/v1/reports/value` et permission `outbound.usage.read` documentée.
- Migration `billing.0006_paidperiodrecord_amount_minor_and_more` requise pour persister le montant/devise du premier paiement; sans elle le test de récompense referral échouait sur `amount_minor` absent.
- Validation locale : Billing + isolation tenant + architecture 30/30; `makemigrations --check --dry-run` sans changement. SQLite ne prouve pas la concurrence PostgreSQL.
- Les tests CRM `test_update_contact_from_order` demandés sous ce nom n'existent pas dans le worktree; le test modifié concerne l'envoi de messages et correspond à `INV-BILL-05/06` et au contrat `SendBulkMessageUseCase`.
- Réconciliation Order Status : contrat partiellement présent dans la documentation, implémentation/tests non trouvés; aucun commit documentaire séparé ne doit être créé sans preuve du code et des tests.
- Prochaines sous-étapes : test Owner sans `plan.manage`, concurrence PostgreSQL du quota, E2E paiement/livraison, contrôles sécurité; un commit par sous-étape.

## 2026-10-23 - Sécurité des permissions Owner

- Ajout d'un test d'intégration prouvant qu'un Owner attribué au scope d'un merchant ne peut pas invoquer une route `plan.manage` globale, même si le rôle contient cette permission.
- Validation : test ciblé `test_merchant_owner_cannot_use_global_plan_manage_permission` réussi (403 attendu).
- Prochaine sous-étape : concurrence du quota sur PostgreSQL réel; SQLite ne valide pas `select_for_update`.

## 2026-10-23 - E2E paiement, livraison et agrégation CRM

- Le parcours E2E existant couvre maintenant les PATCH statut `paid_not_delivered` puis `paid_and_delivered`, le relais de chaque Outbox via Redis et l'agrégation du montant/historique CRM uniquement à la livraison.
- Le scénario a révélé un argument `entitlements` surnuméraire dans le wiring `UpdateOrderStatusUseCase`, corrigé dans le composition root.
- Validation : `tests.integration.test_e2e_message_to_dormant_order` réussi avec SQLite et Redis local.
- Prochaine sous-étape : test concurrent du quota sur PostgreSQL; PostgreSQL local accepte les connexions TCP mais l'authentification est indisponible sans mot de passe.

## 2026-10-23 - Test concurrent du quota Billing

- Ajout d'un `TransactionTestCase` à deux threads, conditionné au support PostgreSQL de `select_for_update`; deux réservations simultanées au quota 1 doivent produire exactement une réservation et un rejet.
- Validation locale : le test est collecté puis ignoré sous SQLite (row locks indisponibles). PostgreSQL local répond sur 5432 mais refuse la connexion sans authentification; aucune preuve réelle de concurrence n'est revendiquée.
- Prochaine sous-étape : suites de sécurité locales, puis exécution du test quota avec PostgreSQL authentifié en CI.

## 2026-10-19 - Phase 3 : messagerie sortante et coûts configurables

- CRM stocke le mode et la catégorie de campagne. `manual_link` est le défaut WhatsApp, génère `wa.me` seulement pour un numéro international validé, et n'appelle jamais le sender. Le worker des campagnes et des relances journalise les propositions sans quota.
- `api_send` route via le capability registry Platform Connectors. Marketing exige une confirmation de l'estimation courante. Billing réserve le quota mensuel idempotemment par destinataire avant chaque appel; le cap est global au merchant, multi-catégorie, et un dépassement garde le destinataire en attente avec `422 OUTBOUND_CAP_REACHED`.
- Les tarifs `OutboundRate` sont administrables par `plan.manage`, pays/devise/catégorie/période; aucun prix Meta n'est seedé faute de grille vérifiée. Estimation sans conversion; Meta facture le vendeur directement, jamais Billing. Mock WhatsApp : `NOT_A_BUSINESS_ACCOUNT` simulé.
- Tests ciblés phase 3 : 43/43 avant ajout du lien de rappel, architecture et routes 7/7, worker rappels 7/7; tests supplémentaires d'upsert tarif et lien de rappel à relancer avant commit. Suite complète différée à la fin phase 4.
- Prochaine étape : phase 4, rapport mensuel de valeur, contrats/routes tenant, CI Billing PostgreSQL, puis validation complète PostgreSQL + Redis réels.

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