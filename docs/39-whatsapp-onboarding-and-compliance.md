# Onboarding WhatsApp et conformité

## Parcours et statut officiel

Parcours guidé : expliquer différence entre compte WhatsApp et WhatsApp Business, sauvegarder les données utiles avec consentement, faire évoluer le vendeur vers l'application Business, reconnecter uniquement via un mécanisme officiellement documenté et autorisé, vérifier les capacités disponibles. « Coexistence » dépend de l'éligibilité produit/fournisseur; vérifier les conditions courantes de Meta avant toute promesse.

À la date de rédaction, aucune API officielle de publication de WhatsApp Status n'est identifiée à notre connaissance; **vérifier la documentation officielle Meta avant toute décision**. L'application prépare la carte, le vendeur la publie lui-même. Disponibilité d'une API officielle pour toute autre fonctionnalité **à vérifier dans la documentation Meta**. Interdits : scraping, émulation, clients/protocoles non officiels ou contournement des limites.

## Use Cases et contrats

| Use Case | Entrée → sortie | Erreurs / événements |
|---|---|---|
| `GuideWhatsAppBusinessOnboardingUseCase` | `{ merchantId, step, locale }` → `{ instructions, nextStep, requirements }` | pack/langue absents; événement analytique agrégé sans PII |
| `CheckWhatsAppBusinessCapabilityUseCase` | `{ connectionId }` → `{ capability, status, guidance }` | capacité inconnue; `PlatformCapabilityChecked` |
| `ImportConversationExportUseCase` | `{ merchantId, file, consentId, selectedRange }` → `{ importId, acceptedCount, rejected[] }` | format/consentement/taille; `ConversationImportCompleted` |
| `AnalyzePastedMessagesUseCase` | `{ merchantId, messages[], consentId }` → `{ analysisIds[], retentionUntil }` | consentement absent/données invalides; `MessagesAnalyzed` |
| `RevokeConversationImportConsentUseCase` | `{ merchantId, consentId }` → `{ revokedAt, deletionStatus }` | déjà révoqué; `ConversationConsentRevoked` |

Mode sans API : import de fichier exporté par l'utilisateur ou collage manuel; analyseurs de format sont configurables et versionnés. Informer des champs extraits, masquer/supprimer médias non requis, éviter de conserver les originaux, permettre aperçu et correction avant traitement.

## P1 — Import manuel implémenté

`POST /api/v1/imports` (`message.import`) exige `consentGiven=true`, `consentId`, plage choisie, un `formatCode` actif et l'entitlement `manual_import`; il retourne 202 et une tâche idempotente par merchant/hash. `GET /api/v1/imports/{id}` ne retourne que l'état au merchant propriétaire. Les contenus stockés sont chiffrés et soumis au plafond HTTP configurable; la tâche est traitée par lots via `process_conversation_imports`, chaque message émettant `MessageReceived` dans la transaction de persistance (INV-IMP-01..04).

| Use Case | Entrée → sortie | Erreurs / événements |
|---|---|---|
| `SubmitConversationImportUseCase` | `{ merchantId, formatCode, content, consentId, consentGiven, selectedRange }` → `{ importId, status: queued, duplicate }` | consentement/plage/format/entitlement/limite invalides; aucun événement avant traitement |
| `GetConversationImportUseCase` | `{ merchantId, importId }` → `{ importId, status, acceptedCount, rejectedCount, errors }` | import absent ou autre tenant → 404; aucun contenu source retourné |
| `ProcessConversationImportUseCase` (job `process_conversation_imports`) | tâche en file → `{ acceptedCount, rejectedCount, status }` | format/données invalides → `failed` ou erreurs bornées; `MessageReceived` par message accepté, Outbox atomique |

Ports : `IImportFormatReader`, `IConversationImportRepository`, `IEntitlementReader`, chiffrement du contenu existant, horloge UTC injectée, Outbox Platform Connectors. Tests attendus : formats JSON/texte fr/en/sw configurés, format inconnu, consentement requis, rejeu/hash, plage UTC inclusive/exclusive, reprise par curseur, contenu chiffré, isolation tenant et émission unique de `MessageReceived`.

Le seed `seed_import_formats` ajoute des formats configurables `json_messages_v1`, `chat_text_fr_v1`, `chat_text_en_v1`, `chat_text_sw_v1`; les variantes réelles d'export restent à confirmer avec des exemples fournis avec consentement. Format inconnu ou inactif: erreur explicite. Les originaux ne sont jamais retournés par l'API d'état.

`NOT_A_BUSINESS_ACCOUNT` : afficher le diagnostic et le parcours guidé de migration/connexion; ne jamais basculer vers un client non officiel ni réessayer sans action du vendeur.

## Agrégats, ports et invariants

Agrégats : `OnboardingJourney`, `ConversationImport`, `ConversationImportConsent`. Ports : `IConversationExportParser`, `IConsentRepository`, `IDataRetentionPolicy`, `IPlatformCapabilityReader`. Réutiliser `MessageReceived`/Rules Engine seulement après validation et consentement, avec idempotence.

`INV-WA-01` pas de lecture/import sans consentement explicite, finalité et plage choisie; `INV-WA-02` import minimisé, aperçu/correction et suppression selon délai configuré; `INV-WA-03` aucune automatisation non officielle; `INV-WA-04` compte/connexion non éligible retourne `NOT_A_BUSINESS_ACCOUNT` ou statut officiel équivalent avec parcours manuel, sans boucle de retry abusive.

Cas limites/tests : archive chiffrée/malformée, export incomplet, pièce jointe volumineuse, message d'un tiers, consentement retiré, doublons, intégrité horodatage, capability absente et erreurs de connexion. Tester suppression, accès tenant, non-publication automatique et absence de contenu dans logs.

Conformité : valider avec Meta les termes, API et limites; avec juriste local la base légale/consentement, droits des participants, transferts, conservation et prospection. Aucune affirmation de compatibilité avant revue. Credentials webhook/API en doc 28; adaptateurs réels interdits sans compte autorisé.
