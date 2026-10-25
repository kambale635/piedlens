# Bounded Context : Mobile Money (`MM`)

## Rôle, agrégats et données

Construire des instructions, analyser des preuves et suivre des paiements via capacités configurables sans détenir l'argent. Agrégats : `MobileMoneyNetwork` (code, pays, capacités, instructions, configuration active), `PaymentEvidence` (origine, données normalisées, confiance, décision) et `PaymentRequest` (référence externe, statut). Le registre résout par code de réseau; secrets/preuves brutes ne sont pas exposés dans les journaux.

| Capacité / port | Responsabilité |
|---|---|
| `IPaymentInstructionBuilder` | Instructions lisibles pour le réseau configuré |
| `IPaymentProofParser` | Extraction configurée de montant, devise, transaction, expéditeur, heure |
| `IPaymentRequestInitiator` | Demande via prestataire; optionnel, jamais simulé comme réel |
| `IPaymentStatusReader` | Interroger statut d'un prestataire configuré |
| `IPayoutSender` | Payout par prestataire agréé, jamais custodie PiedLens |
| `IMobileMoneyNetworkRegistry` | Résoudre `networkCode -> adapter/capabilities` |

## Use Cases

| Use Case | Entrée → sortie | Erreurs / événements |
|---|---|---|
| `BuildPaymentInstructionsUseCase` | `{ merchantId, networkCode, amount: Money, orderId }` → `{ instructions, reference }` | réseau/devise non supportés; aucun mouvement de fonds |
| `SubmitPaymentProofUseCase` | `{ merchantId, orderId, source, payload, consentId }` → `{ evidenceId, confidence, status }` | preuve absente, doublon de transaction, consentement manquant; `PaymentEvidenceSubmitted` |
| `ParsePaymentConfirmationUseCase` | `{ networkCode, message, receivedAt }` → `{ candidate, confidence, issues[] }` | aucun parse fiable; `PaymentEvidenceParsed` |
| `InitiatePaymentRequestUseCase` | `{ merchantId, orderId, networkCode, amount, idempotencyKey }` → `{ requestId, providerReference, status }` | capacité absente, prestataire indisponible; `PaymentRequestInitiated` |
| `HandleAggregatorPaymentWebhookUseCase` | `{ networkCode, rawBody, signature, timestamp }` → `{ accepted, outcome }` | signature invalide, replay, payload inconnu; `ExternalPaymentReceived` après rapprochement |
| `ReconcileExternalPaymentUseCase` | `{ evidenceId }` → `{ outcome, orderId?, status? }` | `DUPLICATE_TRANSACTION`, `AMOUNT_MISMATCH`; réutilise `ExternalPaymentReceived` existant |

Contrat API proposé : `GET /api/v1/orders/{id}/payment-instructions` (`order.read`), `POST /api/v1/orders/{id}/payment-proofs` (`mm.proof.submit`), `POST /api/v1/admin/mobile-money-networks` (`mm.configure`, permission plateforme), webhook `POST /api/v1/webhooks/mobile-money/{network_code}` (`@public_route`, signature timestampée et anti-rejeu). Erreurs normalisées selon doc 22.

## Confiance, idempotence et invariants

Priorité de confiance configurable : webhook signé d'agrégateur > SMS avec identifiant de transaction unique > capture d'écran. Ce classement est une politique initiale à valider; aucune source ne confirme seule le paiement si données discordantes ou seuil non atteint. Rejeter un identifiant de transaction déjà associé à un autre paiement. SMS parser par modèles configurables (champs, regex, séparateurs, locale), aucun modèle linguistique codé dans le domaine.

`INV-MM-01` preuve ne vaut pas paiement final avant rapprochement; `INV-MM-02` transaction ID unique par réseau/compte marchand; `INV-MM-03` Money/devise et montant doivent concorder avec la commande, sinon revue manuelle; `INV-MM-04` seul un prestataire agréé initie un mouvement réel; `INV-MM-05` événement, marqueur idempotent et mutations locales sont transactionnels.

Événements : `PaymentEvidenceSubmitted`, `PaymentEvidenceParsed`, `PaymentRequestInitiated`, et `ExternalPaymentReceived` réutilisé sans nouveau doublon. Tests : modèles fr/en configurés, champs ambigus, duplicate ID, mauvais montant/devise, signatures/replay webhook, sources contradictoires, réseau manquant, retries idempotents et instructions sans adapter réel.

## Configuration et extension

RDC: M-Pesa, Airtel Money, Orange Money et Afrimoney marqués à valider par opérateur/pack. Démarrer avec instructions manuelles et parsing désactivé tant que modèles non validés. Ajouter un réseau = une ligne CountryPack/registre, capacités déclarées, tests de conformité; adaptateur optionnel. Identifiants d'agrégateur et passerelle SMS uniquement dans doc 28, jamais ici.
