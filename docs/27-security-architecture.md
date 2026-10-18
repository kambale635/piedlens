# Architecture de securite

## Modele de menaces

Les actifs sensibles sont les identifiants de session, les tokens des plateformes, les messages clients, les donnees de paiement, les donnees d'identite et les exports. Les menaces retenues pour le MVP sont le vol d'identifiants, le rejeu de webhooks, l'acces inter-tenant, l'exposition accidentelle dans les logs ou exports, la compromission d'une cle et l'exploitation d'une dependance vulnerable.

Les frontieres de confiance sont les requetes HTTP entrantes, les webhooks externes, Redis, PostgreSQL, le stockage d'exports et les workers. Le principe de defense est le refus par defaut : une politique d'acces, un secret, une configuration CORS ou une capacite qui manque ne doit pas etre implicitement autorise.

## Controles requis

- Les secrets de production proviennent de l'environnement ou d'un gestionnaire de secrets. Le demarrage de production echoue si un secret requis manque; aucune cle par defaut n'est admise.
- Les tokens de plateformes sont chiffres avec un algorithme authentifie et des cles versionnees. La version de cle est stockee avec le ciphertext; une rotation permet de lire les anciennes versions pendant leur re-chiffrement.
- Les access tokens ont une duree courte. Les refresh tokens tournent a chaque usage, le rejeu d'un ancien token est detecte et la session correspondante est revoquee. La deconnexion et la revocation globale sont explicites. L'anti-bruteforce applique un backoff progressif et les mots de passe utilisent les validateurs Django. Seul un port TOTP est prepare, sans livraison d'un second facteur dans ce jalon.
- Les signatures de webhook sont comparees en temps constant. Les horodatages sont bornes par une tolerance configurable et une cle d'evenement est mise en cache dans Redis pour bloquer les replays.
- Chaque route resolue a une politique d'acces explicite. Un test parcourt le routeur complet et echoue si une route n'a pas de politique; les tests de tenant prouvent qu'un merchant ne lit ni ne modifie les donnees d'un autre.
- Les en-tetes de securite, HSTS, cookies securises et taille maximale de requete sont configures. CORS est strict et configurable par environnement, desactive par defaut en production.
- L'audit est en ajout seul. Les corps de message, donnees de paiement, tokens et secrets ne sont jamais journalises; un test capture les logs pendant les parcours sensibles.
- Le contenu des messages persiste et les exports sont chiffres applicativement, sauf decision documentee qui nomme explicitement le risque residuel et son alternative.
- La CI execute Bandit, pip-audit et un scan de secrets; toutes les dependances directes et transitives sont figees.

## Matrice de preuves

Cette matrice distingue l'etat constate a la reprise des preuves qui doivent etre ajoutees. Une ligne ne passe a « valide » qu'apres execution du test cite.

| Controle | Etat initial verifie | Preuve attendue |
|---|---|---|
| Secrets de production | Valide pour les secrets applicatifs declares et conditionnellement S3; les settings de test n'exigent aucune valeur. | `tests/unit/test_production_security_settings.py` couvre les secrets obligatoires, debug production et configuration S3. |
| Chiffrement et rotation des tokens | AES-256-GCM versionne; le format historique est lisible via la cle `legacy`; commande de rotation par connexion dans une transaction distincte. | `tests/unit/platform_connectors/test_security_adapters.py` et `tests/integration/platform_connectors/test_token_rotation.py` couvrent round-trip, transition de version et rotation des valeurs persistantes. |
| Cycle de vie d'authentification | Sessions Identity persistees par hash; refresh tourne atomiquement; rejeu revoque la famille; logout individuel/global invalide aussi les access tokens; validateurs Django et backoff exponentiel plafonne; TOTP reste un port. | `tests/integration/identity/test_session_lifecycle.py`, `tests/unit/identity/test_auth_security.py`, `tests/unit/identity/test_identity_use_cases.py` et `tests/integration/identity/test_identity_api.py`. |
| Signature et rejeu des webhooks | HMAC-SHA256 timestamp-aware, comparaison temps constant, tolerance positive configurable, claim atomique Redis apres signature et avant parsing. | `tests/unit/platform_connectors/test_security_adapters.py`, `tests/unit/platform_connectors/test_platform_connector_use_cases.py` et `tests/integration/platform_connectors/test_webhook_replay_cache.py`. Le format reste mock-generique, pas un adaptateur fournisseur reel. |
| Isolation tenant et politiques | Partiel : middleware de permission et tenant presents, mais pas de parcours exhaustif des routes. | Test du resolver Django parcourant chaque route et test A-vers-B lecture/ecriture. |
| En-tetes, cookies, taille et CORS | HSTS, cookies securises et HTTPS forces en production; nosniff, referrer/frame headers; CORS exact, desactive par defaut; corps HTTP limite. | `tests/unit/middleware/test_http_security.py` couvre les en-tetes, defaults production, CORS refuse et 413. |
| Audit et logs | `event_bus_audit_log` n'accepte que des metadonnees; managers/modeles refusent mutation/suppression et PostgreSQL installe un trigger; exception logs contiennent correlation ID + type uniquement. | `tests/integration/test_audit_log_security.py` capture des logs et verifie append-only ORM; test SQL conditionnel au PostgreSQL CI. |
| Chiffrement messages et exports | AES-256-GCM versionne sur messages Platform Connectors, payload Outbox/Redis, snapshots et exports PostgreSQL/S3, et templates de campagnes CRM. Chaque keyring a une commande de rotation par ligne/objet. | `tests/integration/platform_connectors/test_platform_persistence.py`, `tests/integration/test_outbox_relay.py`, `tests/integration/backup/test_backup_exports.py`, `tests/unit/backup/test_backup_payload_cipher.py`, `tests/integration/crm/test_campaign_content_encryption.py`, `tests/unit/test_encrypted_message_event_handler.py`. |
| Dependances et pipeline CI | Versions runtime et transitives figees dans `requirements.txt`; jobs Bandit, pip-audit et Gitleaks ajoutes mais non executes localement (outils absents). | Le workflow doit passer avec `bandit -r src -ll`, `pip-audit -r requirements.txt`, Gitleaks et la suite PostgreSQL/Redis. |

## Decisions encore a prendre

- Le chiffrement applicatif des messages et exports doit etre prefere. Si son integration avec la sauvegarde ou la recherche rend une operation disproportionnee, documenter avant de choisir l'alternative, ses limites d'exposition et sa cle de chiffrement.
- Les secrets de fournisseurs reels ne sont pas necessaires aux tests : les adaptateurs restent mock. Aucun secret de production n'est stocke dans le depot ou demande dans une conversation.
- Le hook Sentry est conditionnel a `SENTRY_DSN`; `sentry-sdk` n'est pas installe dans l'environnement actuel et ne sera ajoute qu'apres accord explicite.