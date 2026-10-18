# Registre des variables de credentials

Ce registre contient des noms de variables uniquement, jamais leurs valeurs. Les tests et le developpement restent sur des adaptateurs mock. Les valeurs de production se configurent directement dans le gestionnaire de secrets/deploiement, jamais dans le depot ni dans une conversation.

| Variable | Provenance | Environnement | Etape dependante |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Generee par l'exploitant avec un generateur cryptographique; stockee dans le gestionnaire de secrets. | Test/staging puis production, valeurs distinctes. | 4, demarrage production. |
| `POSTGRES_PASSWORD` | Generee et geree par l'administrateur de la base/deploiement. | Test/staging puis production, valeurs distinctes. | 4, PostgreSQL/Compose. |
| `REDIS_URL` | Fournie par l'exploitant Redis; toute authentification incluse reste dans le gestionnaire de secrets. | Test/staging puis production. | 4, anti-rejeu et cache. |
| `PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION` | Version active (par exemple `v1`), sans valeur secrete. | Valeurs configurees par environnement. | 4, selection de la cle de chiffrement active. |
| `PLATFORM_TOKEN_ENCRYPTION_KEY_<VERSION>` | Cle 256 bits URL-safe base64 generee par l'exploitant ou fournie par le KMS. | Une cle distincte par version et environnement. | 4, chiffrement et rotation des tokens. |
| `PLATFORM_TOKEN_ENCRYPTION_KEY` | Nom historique accepte uniquement pour lire des ciphertexts non versionnes durant une migration; a retirer apres rotation confirmee. | Ancienne valeur de l'environnement source seulement. | 4, compatibilite transitoire pendant `rotate_platform_tokens`. |
| `BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION` | Version active (par exemple `v1`), sans valeur secrete. | Valeur distincte par environnement. | 4, chiffrement applicatif des objets snapshot/export. |
| `BACKUP_DATA_ENCRYPTION_KEY_<VERSION>` | Cle 256 bits URL-safe base64 generee par l'exploitant ou fournie par le KMS. | Une cle distincte par version et environnement. | 4, chiffrement et rotation via `rotate_backup_payloads`. |
| `PLATFORM_MESSAGE_ENCRYPTION_ACTIVE_VERSION` | Version active (par exemple `v1`), sans valeur secrete. | Valeur distincte par environnement. | 4, chiffrement du message en base et de sa copie Outbox. |
| `PLATFORM_MESSAGE_ENCRYPTION_KEY_<VERSION>` | Cle 256 bits URL-safe base64 generee par l'exploitant ou fournie par le KMS. | Une cle distincte par version et environnement. | 4, chiffrement et rotation via `rotate_platform_message_content` du contenu message/Outbox. |
| `CRM_MESSAGE_ENCRYPTION_ACTIVE_VERSION` | Version active (par exemple `v1`), sans valeur secrete. | Valeur distincte par environnement. | 4, chiffrement des templates de campagnes CRM sauvegardes. |
| `CRM_MESSAGE_ENCRYPTION_KEY_<VERSION>` | Cle 256 bits URL-safe base64 generee par l'exploitant ou fournie par le KMS. | Une cle distincte par version et environnement. | 4, chiffrement et rotation via `rotate_campaign_content`. |
| `WHATSAPP_WEBHOOK_SECRET` | Console de developpeur du fournisseur; credential absent tant qu'aucun compte n'est provisionne. | Sandbox d'abord; live seulement apres autorisation explicite. | 4, webhook signe; adaptateur reel bloque en attendant. |
| `INSTAGRAM_WEBHOOK_SECRET` | Console de developpeur du fournisseur; credential absent tant qu'aucun compte n'est provisionne. | Sandbox d'abord; live seulement apres autorisation explicite. | 4, webhook signe; adaptateur reel bloque en attendant. |
| `FACEBOOK_WEBHOOK_SECRET` | Console de developpeur du fournisseur; credential absent tant qu'aucun compte n'est provisionne. | Sandbox d'abord; live seulement apres autorisation explicite. | 4, webhook signe; adaptateur reel bloque en attendant. |
| `BACKUP_EXPORT_SIGNING_SECRET` | Generee par l'exploitant avec un generateur cryptographique; stockee dans le gestionnaire de secrets. | Valeurs distinctes par environnement. | 4, liens d'export signes. |
| `BACKUP_DELETE_CONFIRMATION_SECRET` | Generee par l'exploitant avec un generateur cryptographique; stockee dans le gestionnaire de secrets. | Valeurs distinctes par environnement. | 4, confirmation de suppression. |
| `HEALTH_METRICS_TOKEN` | Genere par l'exploitant avec un generateur cryptographique et partage uniquement avec le collecteur de metriques. | Valeurs distinctes par environnement. | 5, acces bearer a `/health/metrics`. |
| `SENTRY_DSN` | Sentry project settings; creer un projet staging avant tout projet live. | Staging puis live apres approbation. | 5, l'envoi d'evenements Sentry attend l'ajout approuve de `sentry-sdk`; ne pas configurer avant cela. |
| `BACKUP_S3_ACCESS_KEY_ID` | Role/service account limite au bucket de sauvegarde, cree par l'administrateur du stockage. | Bucket de staging avant tout bucket live. | 5, adaptateur S3 reel; non requis avec le stockage PostgreSQL. |
| `BACKUP_S3_SECRET_ACCESS_KEY` | Gestionnaire de secrets du fournisseur de stockage, associe au role limite ci-dessus. | Bucket de staging avant tout bucket live. | 5, adaptateur S3 reel; non requis avec le stockage PostgreSQL. |

Les trois secrets webhook de fournisseur et les identifiants S3 ne sont pas demandes maintenant. Leur absence bloque uniquement l'activation de ces integrations reelles; les parcours mock restent utilisables.