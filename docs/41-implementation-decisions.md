# Décisions et règles d’implémentation Afrique

Ce document est la source de décision pour les phases P1–P6. Il prévaut sur les docs 30–39 en cas de différence.

## Principes

Plateforme de commerce social configurable, canaux et paiements interchangeables; WhatsApp n’est qu’un adaptateur. Le vendeur valide toute négociation, publication, envoi et action financière. Aucun fonds détenu par la plateforme; séquestre uniquement via prestataire agréé. Statut WhatsApp : aucune API officielle de publication connue à date, à revérifier chez Meta; publication manuelle seulement, aucun scraping/client non officiel. IA = suggestions seulement; pas d’entraînement sur les messages. Assistants généralistes annoncés interdits par Meta depuis le 15/01/2026, source à vérifier avant usage. Juristes locaux : paiements, escrow, KYC/AML, données, fiscalité, consommateurs, logistique et fournisseurs.

## D1–D8 — Décisions

- **D1 Canaux agnostiques** : capacité `ConversationSource` du registre, événement normalisé `MessageReceived`; ajout = adaptateur + ligne `ChannelConfig`. Noms fournisseur absents de domain/application, hors adaptateurs.
- **D2 Intake sans API** : export ou texte collé, `ImportFormat` versionné en base (seed fr/en/sw), format inconnu rejeté; consentement, minimisation, taille bornée, traitement asynchrone.
- **D3 WhatsApp Status** : publication manuelle par vendeur; attribution par code de suivi; aucun automatisme non officiel.
- **D4 Payments** : contexte `payments`; `PaymentProviderRegistry`, `PaymentRoute` (pays/devise/méthode/provider/priorité/actif). Ports `ICheckoutInitiator`, `IPaymentWebhookVerifier`, `IPaymentStatusReader`, `IPaymentProofParser`, `IPayoutSender`, `IRefundIssuer` dans shared kernel. Endpoint `/webhooks/payments/{provider}`, signature/anti-rejeu/idempotence; démarrage avec `Idempotency-Key`. Adaptateurs mock couvrent succès/échec/attente/tardif/doublon et `manual_proof`; squelettes FlexPay/MaxiCash/pawaPay échouent clairement sans credentials. `SettlementAccount` vérifié, split frais; jamais de custodie; `supports_escrow` explicite.
- **D5 Preuves** : `unverified`, `seller_confirmed`, `provider_confirmed`; SMS par réseau en config, motifs à valider avec vrais SMS; transaction ID unique; réutiliser `ExternalPaymentReceived` et rapprochement Order Detection.
- **D6 IA** : règles configurables et approbation vendeur; aucun entraînement sur messages.
- **D7 FX** : taux saisis par vendeur, paire/valeur/source/date/historique; `RateSnapshot` immuable par transaction; arrondi configurable; conversion interdite sans snapshot (amende `INV-CRM-08`, `INV-OD-05`, `INV-TR-05`).
- **D8 Extensibilité** : tests enregistrent `fake_channel`, `fake_payment_provider`, un réseau Mobile Money par configuration seule et exécutent les flux sans modifier les implémentations existantes.

## T1–T10 — Intégrité

- **T1 / INV-TR-01** : un agrégat modifié par transaction. Multi-agrégats par événements Outbox/process manager idempotent et compensable; paiement sans stock => `needs_review` + remboursement demandé.
- **T2** : événement Outbox dans la transaction du changement; consumers idempotents via `processed_events`.
- **T3** : PostgreSQL READ COMMITTED; `select_for_update` ou UPDATE versionné sur stock, PaymentAttempt, PurchaseOrder, Order, SettlementAccount; ordre de verrouillage déterministe et retries bornés.
- **T4** : CHECK montants/stock non négatifs, UNIQUE clés naturelles d’idempotence, NOT NULL, FK intra-contexte, index `merchant_id` et toutes lectures tenant filtrées.
- **T5** : `Money` entier en unités mineures, devise obligatoire; montant jamais fourni par le client, recalcul serveur et snapshots immuables prix/devise/taux.
- **T6** : transitions uniquement dans agrégats; `DomainException` cite l’INV; tests table-driven pour transitions valides et invalides.
- **T7** : idempotence webhook, consumers, imports par hash, commandes publiques et démarrage paiement; même clé/contenu = réponse stockée, contenu différent = 409.
- **T8** : UTC et horloge injectée; expiration/réconciliation en jobs.
- **T9** : `PaymentEvent`, `StockMovement`, `PayoutInstruction` append-only; UPDATE/DELETE refusés et testés.
- **T10** : aucun PAN/carte, contenu message ou SMS dans les logs.

## Invariants métier et états

- **PAY** : `INV-PAY-01` montant/devise PaymentAttempt immuables, écart webhook => `needs_review`; `02` un effet par event provider, un succès par payable, second => `duplicate_payment` + remboursement; `03` preuve `unverified` ne confirme pas; `04` reversement vers compte vérifié uniquement; `05` frais fixés à création; `06` `created -> pending -> succeeded|failed|expired|cancelled`, `succeeded -> partially_refunded|refunded`, tardif après expiration => `needs_review`, monotone et job de rapprochement; `07` paiement partiel interdit V1, exact ou `needs_review`.
- **CAT / INV-CAT-01** : stock jamais négatif via CHECK + décrément atomique; réservation expirante libérée en job; mouvements idempotents par commande.
- **STO / INV-STO-01** : total recalculé serveur et snapshot immuable; **INV-OD-10** commande storefront explicite hors seuils de détection.
- **FX / INV-FX-01** : aucune conversion sans `RateSnapshot` explicite immuable.
- **PRC / INV-PRC-01** : offre jamais sous plancher; plancher ni exposé ni journalisé.
- **PO / INV-PO-01** : `draft -> submitted -> accepted|rejected`; `accepted -> paid -> shipped -> delivered -> completed`; litige depuis `paid|shipped|delivered`; annulation avant expédition. **02** reversement UNIQUE/PurchaseOrder, code validé ou délai configuré, retries puis `needs_review`. **03** avis après `completed`. **04** code de remise haché, cinq essais maximum.
- **SUP / INV-SUP-01** : vérification téléphone/identité/entreprise/références monotone, révocable avec audit; documents chiffrés; score explicable/configurable.
- **IMP / INV-IMP-01** : consentement avant import, idempotence, job reprenable; chaque lot/élément a sa transaction.

## Phases

| Phase | Livraison |
|---|---|
| P1 | Intake agnostique, import manuel consenti, formats fr/en/sw, événement `MessageReceived`. |
| P2 | Payments D4/D5/INV-PAY; changement plan via `PaymentSucceeded`, échec avec grâce configurable, lien de paiement Order. |
| P3 | Catalogue/variantes/unités/prix/stock/mouvements/alertes/CSV/photos; boutique publique sans PII, commandes sans compte rate-limitée, Order `pending_payment`, CRM; kit de partage vendeur. |
| P4 | Status Studio, cartes/légendes/code de suivi, Rules Engine `TrackingCodeMatch`, attribution, rappel manuel, ventes par carte. |
| P5 | Taux vendeur, listes/remises/plancher privé, `NegotiationThread`, contre-offres au-dessus plancher approuvées, prix final Order, rapport marge perdue. |
| P6 | `supplier_features`; profil/VerificationCase, SMS mock, documents chiffrés, revue personnel `supplier.verify`, score, gros/PO, paiements/reversements SettlementAccount, code, avis, logistique. |

P2–P6 exécutées dans l’ordre, une phase verticale par commit. Au début de chaque phase, invariants et états ajoutés à docs/16, avant code.

## Concurrence, sécurité et sortie

En PostgreSQL réel avec `REQUIRE_POSTGRES=1`, les tests obligatoires couvrent : webhooks identiques parallèles/un effet; commandes concurrentes dernière unité/une réussite; démarrages même `Idempotency-Key`/une tentative; reversements concurrent/PurchaseOrder unique; rollback injecté après écriture/ni état ni Outbox partiel; UPDATE/DELETE refusés sur ledgers append-only. Tout test ignoré en CI fait échouer le job.

Routes publiques : `@public_route` + rate limit, aucune PII publique; isolation tenant, permissions dans docs/24 + seed rôles; entitlements `storefront_enabled`, `max_products`, `manual_import`, `supplier_features` via `IEntitlementReader`. Terminé : P1–P6 committées, D8 et architecture D1 verts, concurrence PostgreSQL CI verte, suite complète verte, docs/16/28/41 et METHODE_REPRISE à jour.
