# Methode de reprise du projet

Ce document guide toute nouvelle conversation ou reprise de session. Il complete `prompt_demarage.txt`, qui sert au demarrage initial du projet; il ne le remplace pas. Ne jamais deduire l'etat du code a partir d'un ancien resume seul : verifier les fichiers et les tests actuels.

## 2026-10-18 — Point de reprise apres l'etape 3a

- Derniere etape terminee : 3a, canaux extensibles de Platform Connectors. Le commit de cette etape est a creer apres verification des chemins stages.
- Prochaine action : etape 4, securite; lire `docs/27-security-architecture.md` apres sa creation et mettre a jour le registre des noms de variables d'environnement.
- Validation ciblee : `./venv/bin/python manage.py test tests.unit.platform_connectors tests.integration.platform_connectors tests.architecture.test_architecture_boundaries --settings=config.test_settings -v 1` (27/27); `./venv/bin/python manage.py makemigrations --check --dry-run --settings=config.test_settings` (aucun changement).
- Suite complete de cette etape : `./venv/bin/python manage.py test tests --settings=config.test_settings -v 1` (155 tests, 1 ignore). Les settings de test utilisent SQLite : ce resultat ne prouve pas les garanties PostgreSQL.
- Pieges connus : Compose ne peut pas etre evalue sans `DJANGO_SECRET_KEY` et `POSTGRES_PASSWORD` dans l'environnement; ne pas lire/afficher `.env`. PostgreSQL local sur 5432 exige un mot de passe; le conteneur `garage_postgres` sur 5433 est un autre projet. Redis local sur 6379 repond `PONG`.
- Les adaptateurs reels ne sont pas implementes. `WHATSAPP_ADAPTER`, `INSTAGRAM_ADAPTER` et `FACEBOOK_ADAPTER` restent `mock` par defaut; `real` echoue clairement. Aucun identifiant tiers requis pour la suite mock.

## 2026-10-18 — Etape 4, sous-etape documentation terminee

- Derniere sous-etape terminee : modele de menaces et matrice des preuves dans `docs/27-security-architecture.md`; les lignes non prouvees restent marquees partielles/manquantes.
- Prochaine action : inspecter les reglages production et leurs tests; exiger les secrets sans valeur par defaut, puis creer/actualiser `docs/28-external-credentials-register.md` avec les noms seulement.
- Verification documentaire : `git diff --check`; aucun test executable ne couvre la seule creation de cette specification. Les tests de chaque controle doivent suivre sa modification.
- Piege : l'environnement courant n'a pas les variables Compose `DJANGO_SECRET_KEY` et `POSTGRES_PASSWORD`; ne pas ajouter de valeurs locales au depot et ne jamais demander leur copie dans le chat.

## 2026-10-18 — Etape 4, secrets de production termines

- Derniere sous-etape terminee : validation fail-fast dans `config/security_settings.py`, testee pour chaque variable requise, `DJANGO_DEBUG=1` et credentials conditionnels S3; registre noms-seulement ajoute dans `docs/28-external-credentials-register.md`.
- Prochaine action : remplacer la cle unique des tokens par un ring de cles versionnees et tester la rotation.
- Test cible : `./venv/bin/python manage.py test tests.unit.test_production_security_settings --settings=config.test_settings -v 1` (5/5).
- Pieges : le module de validation est pur et teste sans config Django de production; ne pas creer de `.env` ou de secret de test commite. Les vrais secrets webhook/provider ne sont pas necessaires pour cette implementation mock.

## 2026-10-18 — Etape 4, rotation des tokens terminee

- Derniere sous-etape terminee : tokens `vN.` AES-GCM authentifies, lecture retrocompatible des ciphertexts historiques via la cle `legacy`, et commande `rotate_platform_tokens` transactionnelle par connexion.
- Prochaine action : Identity, en commençant par le contrat actuel de refresh dans `docs/15-use-cases-catalog.md` et `docs/25-context-identity.md`; la rotation/revocation exige probablement une migration et des contrats de session.
- Tests : `./venv/bin/python manage.py test tests.integration.platform_connectors.test_token_rotation tests.unit.platform_connectors.test_security_adapters tests.unit.test_production_security_settings --settings=config.test_settings -v 2` (12/12).
- Pieges connus : fournir simultanement ancienne et nouvelle cle pendant rotation; la commande ne peut dechiffrer des lignes legacy si l'ancienne cle n'est pas dans le keyring. Les cles sont des secrets de deploiement, jamais des valeurs de test commitees.

## 2026-10-18 — Etape 4, contrat Identity etendu

- Contrat documente avant code dans `docs/15-use-cases-catalog.md` : refresh retourne les deux tokens; un rejeu invalide la famille; logout est idempotent; logout-all agit sur le principal courant uniquement.
- `docs/25-context-identity.md` declare le stockage du hash du refresh token, le port de backoff progressif et le port TOTP (sans implementation TOTP).
- Prochaine action : ajouter les sessions persistantes Identity et adapter routes/tests selon ces contrats.
- Aucun nouveau secret tiers n'est requis; tests avec tokens signes locaux uniquement.

## 2026-10-18 — Etape 4, cycle d'authentification termine

- Derniere sous-etape terminee : migration `identity.0005_authsessionrecord`, refresh rotatif avec detection/revocation de famille, logout, logout-all, access tokens lies a une session, validateurs Django, backoff progressif et port TOTP seul.
- Prochaine action : horodatage signe, tolerance configurable et cache Redis anti-rejeu pour les webhooks.
- Tests passes : `tests.integration.identity.test_session_lifecycle` 3/3; `tests.unit.identity.test_auth_security` 2/2; `tests.unit.identity.test_identity_use_cases` + `tests.integration.identity.test_identity_api` 8/8, tous avec `--settings=config.test_settings`.
- Piege migration : les refresh tokens pre-`identity.0005` sont stateless et seront refuses; prevoir reconnexion utilisateur au deploiement. `logout-all` invalide aussi les access tokens car chaque requete verifie l'etat de session.
- Aucun TOTP effectif, SMS, fournisseur externe ni secret live n'a ete ajoute.

## 2026-10-18 — Etape 4, webhooks securises

- Derniere sous-etape terminee : signature HMAC timestamp-aware, comparaison constante, anti-rejeu par `cache.add` Redis apres signature valide et avant parsing; horodatage ASCII canonique uniquement.
- Prochaine action : test exhaustif des politiques de routes/tenant, puis en-tetes securite, limites requete, audit append-only et capture des logs.
- Test passe : `./venv/bin/python manage.py test tests.unit.platform_connectors tests.integration.platform_connectors.test_webhook_replay_cache --settings=config.test_settings -v 1` (20/20).
- Piege : le format timestamp-plus-corps est un contrat mock generique et n'est pas compatible par declaration avec Meta; implementer le format natif uniquement dans un adaptateur reel apres fourniture explicite des credentials. Le test de cache cible Redis local, pas Redis Compose du projet.

## 2026-10-18 — Etape 4, routes/HTTP/audit

- Derniere sous-etape terminee : politique explicite verifiee sur tout le resolver; test HTTP de scope A/B sur toutes les routes permissionnees plus lecture/ecriture CRM; HSTS/cookies/HTTPS, headers browser, CORS exact, limites corps et audit append-only ajoutes.
- Prochaine action : traiter le chiffrement applicatif des messages/exports (ou documenter une alternative), puis CI bandit/pip-audit/secret scan et versions figees.
- Validation combinee : `./venv/bin/python manage.py test tests.integration.test_audit_log_security tests.unit.middleware.test_http_security tests.integration.test_tenant_route_isolation tests.architecture.test_route_security_policy --settings=config.test_settings -v 1` (12 trouves, 11 passes, 1 trigger PostgreSQL saute sous SQLite).
- Le trigger PostgreSQL est migre uniquement sur PostgreSQL; le test SQL conditionnel n'a pas pu etre prouve ici. Le test ORM append-only passe sous SQLite.
- CORS n'ajoute jamais `Access-Control-Allow-Credentials`; ajouter uniquement des origines exactes via `CORS_ALLOWED_ORIGINS`. Taille max vient de `DJANGO_MAX_REQUEST_BODY_BYTES`.

## 2026-10-18 — Etape 4, chiffrement applicatif des contenus

- Derniere sous-etape terminee : AES-256-GCM versionne pour messages platform, copie Outbox/Redis, objets Backup PostgreSQL/S3 et templates CRM; registre 28 actualise avec noms de keyrings seulement.
- Test passe : `./venv/bin/python manage.py test tests.integration.backup.test_backup_exports tests.integration.crm.test_campaign_content_encryption tests.integration.platform_connectors.test_platform_persistence tests.integration.test_outbox_relay tests.unit.test_encrypted_message_event_handler tests.unit.backup.test_backup_payload_cipher --settings=config.test_settings -v 1` (20 trouves, 19 passes, 1 PostgreSQL skip).
- Commandes de rotation : `rotate_platform_tokens`, `rotate_platform_message_content`, `rotate_backup_payloads`, `rotate_campaign_content`; elles re-chiffrent par ligne/objet. Ne retirer aucune ancienne cle avant rotation terminee et verifiee.
- Les cles deterministes de `config.test_settings.py` sont exclusivement pour tests, jamais pour production.

## 2026-10-18 — Etape 4, scans CI et dependances

- Derniere sous-etape terminee : versions runtime/transitives epinglees; workflow Bandit/pip-audit/Gitleaks; `config.ci_settings` garde PostgreSQL/Redis et injecte des keyrings non-production.
- Prochaine action : lancer une seule suite complete locale, puis finaliser le commit de l'etape 4 et le rapport de reprise.
- Controles passes : `manage.py check --settings=config.ci_settings`, round-trip des quatre keyrings CI, `pip check`, `git diff --check`.
- Les scanners sont absents du venv et n'ont pas ete installes localement; ils sont installes/executés dans le job CI. Ne pas installer localement sans demande.
- PostgreSQL Compose du projet reste inaccessible faute des variables requises; SQLite ne prouve ni les locks ni le trigger append-only. Redis localhost repond pour les tests Streams/cache.
- Limites securite : workflow CI distant pas encore observe; PostgreSQL natif/trigger non prouves localement; reconnexion requise pour anciens tokens Identity stateless; TOTP seulement un port; adaptateurs/credentials fournisseurs live absents.

## 2026-10-18 — Etape 5, exploitation

- Derniere sous-etape terminee : endpoints live/ready/metrics, lag Outbox et taille DLQ avec seuils/hook, logs JSON, arret cooperatif SIGTERM/SIGINT, grace Compose 60s et runbook de sauvegarde/restauration PostgreSQL dans `docs/29-operations-runbook.md`.
- Prochaine action : scenario E2E 6b, transitions paiement/livraison puis totaux CRM.
- Validation : `./venv/bin/python manage.py test tests.unit.test_operational_health_and_logging tests.integration.test_operational_metrics tests.unit.test_observability tests.architecture.test_route_security_policy --settings=config.test_settings -v 1` (14/14); `docker compose config -q` reussi avec valeurs jetables; `manage.py check` reussi.
- Sentry est cable via `SENTRY_DSN`, mais `sentry-sdk` n'est pas present dans le venv. Conformement a la consigne, aucune installation locale; l'activation reelle attend l'approbation d'ajouter cette dependance et la creation d'un DSN staging. Variable seule dans docs/28.
- La validation PostgreSQL du trigger audit et des scenarios avec DB reelle reste impossible sans credentials; Redis localhost fonctionne.

## 2026-10-18 — E2E 6a termine

- Derniere sous-etape terminee : webhook signe -> Outbox plateforme -> Redis Streams -> Rules Engine et CRM -> Outbox rules -> consumer Order Detection -> `pending_payment` -> GET dashboard `15000.0000 XOF`; Contact cree via son consumer.
- Test : `./venv/bin/python manage.py test tests.integration.test_e2e_message_to_dormant_order --settings=config.test_settings -v 1` (1/1, SQLite + Redis local). CI reutilise ce scenario avec PostgreSQL/Redis.
- Defaut corrige : `Money` est converti en `{amount,currency}` avant JSON dans `DjangoRulesEngineOutbox`.
- Prochaine sous-etape : E2E 6b, commande payee puis livraison confirmee.

## 1. Retrouver le bon etat

1. Confirmer le dossier racine du workspace et identifier les fichiers reellement presents. Ne pas supposer que Git, Docker, PostgreSQL ou des services locaux sont disponibles.
2. Lire integralement `.github/copilot-instructions.md`.
3. Lire integralement `evolution.md`. Reperer la derniere etape terminee, ses validations, les limites connues et le prochain travail autorise. Verifier ensuite cet etat dans le code et les tests.
4. Lire `docs/00-README.md` et les documents directement applicables au travail. Pour un Use Case, lire au minimum son contrat dans `docs/15-use-cases-catalog.md`, le document du bounded context, les invariants de `docs/16-business-invariants-and-rules.md`, puis les standards necessaires (`docs/17-documentation-standards.md`, `docs/22-error-handling-and-exceptions.md`, `docs/23-shared-kernel-value-objects.md`, `docs/14-event-driven-architecture.md`).
5. Lire l'implementation voisine, les ports, l'infrastructure, le wiring et les tests qui controlent le comportement. Identifier le vrai proprietaire de la decision avant toute modification.
6. Si une regle metier, une erreur, une transaction ou un contrat est ambigu ou contradictoire, ne pas inventer de valeur ni de comportement : exposer precisement la contradiction et demander une decision.

## 2. Une seule tache a la fois

- Respecter la regle 19 de `.github/copilot-instructions.md` : terminer une seule tache delimitee avant d'en commencer une autre.
- Suivre l'ordre explicitement valide par le proprietaire. Un feu vert pour une tache n'autorise pas automatiquement la suivante.
- Avant le code, confirmer le contrat, les invariants, les ports, les effets transactionnels et les cas d'erreur.
- Ecrire ou adapter un test de comportement cible, effectuer la plus petite modification coherente, puis lancer immediatement ce test.
- Ne pas presenter une hypothese comme une regle validee. Les seuils, politiques et valeurs variables viennent de la configuration documentee; pas de constantes metier improvisees.
- A la fin, mettre a jour `evolution.md` avec les fichiers touches, les validations reelles, les echecs ou limites et la prochaine etape. Presenter le bilan au proprietaire et attendre son feu vert.

## 3. Regles d'architecture et d'atomicite

- Respecter Clean Architecture, DDD, SOLID et les frontieres de bounded context. Le domaine ne depend pas de Django, ORM, Redis ou d'un autre contexte.
- Injecter les ports dans les Use Cases. Les adapters concrets et leur assemblage restent dans l'infrastructure et le composition root.
- Une operation modifie un seul Aggregate Root. Toute communication entre contextes passe par un contrat expose ou un evenement, jamais par un repository d'un autre contexte.
- Pour une ecriture qui emet un evenement, enregistrer l'agregat/la notification et l'evenement Outbox dans la meme transaction `transaction.atomic()` via le UnitOfWork du contexte (INV-TR-01/02). Ne jamais faire de dual-write base + Redis depuis le Use Case.
- Tout consumer evenementiel verifie et inscrit son marqueur `processed_events` dans la meme transaction que ses changements metier (INV-TR-03).
- Un adaptateur n'est transactionnel avec le UnitOfWork que si ses requetes utilisent la meme connexion/base active. Le demontrer par un test de commit et de rollback; ne pas conclure a l'atomicite sur la seule presence d'un context manager.

## 4. Commandes locales de validation

Pour les tests unitaires purs :

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit/crm -p 'test_*.py' -v
```

Pour les tests Django d'integration, utiliser les settings de test du depot, pas les settings par defaut qui ciblent PostgreSQL :

```bash
python3 manage.py test tests.integration.crm --settings=config.test_settings -v 2
```

Pour verifier les migrations CRM :

```bash
python3 manage.py makemigrations crm --check --dry-run --settings=config.test_settings
```

Les tests locaux utilisent SQLite en memoire via `config.test_settings`; les settings standards requierent une configuration PostgreSQL. Une erreur d'authentification PostgreSQL ou de daemon Docker est un probleme d'environnement a diagnostiquer separement, pas la preuve d'un defaut applicatif. SQLite valide les commits/rollbacks dans ces tests mais ne prouve pas le comportement de concurrence PostgreSQL (`select_for_update`, `skip_locked`); conserver une validation PostgreSQL CI pour ces garanties.

Ne jamais afficher, copier dans le code ou commiter un secret. Utiliser les variables d'environnement et les fichiers d'exemple sans valeurs sensibles.

## 5. Point de reprise actuel

Etat verifie le 2026-09-28 :

- CRM : Outbox transactionnelle, historique d'achats CRM, alertes d'anomalie configurées et `MergeContactsUseCase` temps 1/2 sont présents. `INV-CRM-04` autorise exclusivement `OrderStatusChanged (paid_and_delivered)` et l'absorption du snapshot `ContactMerged`.
- Order Detection : les Use Cases du catalogue déjà couverts, dont le consommateur `ReassignContactReferencesFromContactMergedUseCase`, sont présents. Ce consumer modifie chaque Order/Candidate dans une transaction séparée et marque l'événement après les deux balayages.
- Dernière validation : tests unitaires CRM 28/28 et intégration CRM 17/17; tests unitaires Order Detection 39/39 et intégration Order Detection 12/12; aucune migration CRM ou Order Detection requise; system checks sans erreur.
- Le consumer CRM `ContactMerged` additionne le snapshot côté Contact principal avec un marqueur CRM atomique. Le consumer Order Detection consomme uniquement les IDs et ignore le snapshot CRM.
- Les achats CRM antérieurs à la migration d'historique ne sont pas reconstruits; aucun accès aux tables Order Detection n'est autorisé depuis CRM.
- **BLOQUANT AVANT MISE EN PRODUCTION** : le relay Outbox et la publication Redis Streams ne sont pas implémentés; les consumers ne sont donc pas branchés à un transport opérationnel. Les tests SQLite ne valident pas les garanties de concurrence PostgreSQL.
- Les écarts de persistance/contrat des segments et envois CRM signalés précédemment doivent encore être audités. Les schémas PostgreSQL natifs par bounded context restent également à configurer.

Apres chaque tache, actualiser cette section si l'etat de reprise change et consigner les resultats dans `evolution.md`.