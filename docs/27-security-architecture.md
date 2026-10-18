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
| Cycle de vie d'authentification | Partiel : access/refresh signes et expirants; rotation, rejeu, revocation et backoff absents. | Tests Identity de rotation, detection de rejeu, logout, revocation globale, backoff et validateurs. |
| Signature et rejeu des webhooks | Partiel : HMAC et comparaison temps constant; tolerance d'horodatage et cache Redis absents. | Tests de signature, horodatage hors fenetre, rejection du rejeu et Redis indisponible. |
| Isolation tenant et politiques | Partiel : middleware de permission et tenant presents, mais pas de parcours exhaustif des routes. | Test du resolver Django parcourant chaque route et test A-vers-B lecture/ecriture. |
| En-tetes, cookies, taille et CORS | Partiel : `SecurityMiddleware` seulement; HSTS, limites et CORS strict non prouves. | Tests Django de reponse, cookies, rejet de corps trop grand et matrice CORS par environnement. |
| Audit et logs | Partiel : audit de metadonnees; ajout-seul et absence de contenu dans les logs non prouves ensemble. | Test de capture des logs sur webhook, message et paiement; test de mutation/suppression de l'audit refusee. |
| Chiffrement messages et exports | Partiel : SSE pour le stockage S3; stockage PostgreSQL et exports applicatifs non chiffres. | Tests de ciphertext au repos et de restitution autorisee, ou decision alternative documentee et testee. |
| Dependances et pipeline CI | Manquant : outils de scan et versions transitives non verifies. | Workflow vert avec Bandit, pip-audit, secret scan et lock de dependances. |

## Decisions encore a prendre

- Le chiffrement applicatif des messages et exports doit etre prefere. Si son integration avec la sauvegarde ou la recherche rend une operation disproportionnee, documenter avant de choisir l'alternative, ses limites d'exposition et sa cle de chiffrement.
- Les secrets de fournisseurs reels ne sont pas necessaires aux tests : les adaptateurs restent mock. Aucun secret de production n'est stocke dans le depot ou demande dans une conversation.