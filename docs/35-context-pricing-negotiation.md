# Bounded Context : Pricing & Negotiation (`PRC`)

## Rôle et agrégats

Proposer un prix cohérent avec les règles du vendeur, sans négocier ni répondre au client sans son accord. Agrégats : `PriceList` (merchant/devise/période), `PriceRule` (paliers/remises), `NegotiationThread` (conversation/Order, propositions versionnées, décision du vendeur). Prix plancher confidentiel : secret métier, jamais renvoyé à l'API client ni journalisé.

## Use Cases

| Use Case | Entrée → sortie | Erreurs / événements |
|---|---|---|
| `SetPriceListUseCase` | `{ merchantId, currency, items[], effectiveAt }` → `{ priceListId, version }` | prix invalide/conflit; `PriceListSet` |
| `ProposeNegotiationUseCase` | `{ merchantId, orderId?, contactId, intent, items, quantity, sourceMessageId }` → `{ threadId, proposal, requiresSellerApproval: true }` | données insuffisantes, demande sous plancher; `NegotiationProposalPrepared` |
| `ApproveCounterOfferUseCase` | `{ merchantId, threadId, proposalId, decision, finalPrice? }` → `{ status, finalPrice? }` | prix sous plancher, stale proposal; `CounterOfferApproved/Rejected` |
| `ReportDiscountMarginUseCase` | `{ merchantId, period, currency }` → `{ lostMarginByReason[] }` | devise explicite requise; rapport en lecture seule |

Règles Rules Engine configurables : intents `price_inquiry`, `price_negotiation`, `last_price_request`, `bulk_request`; PRC ne code pas leurs mots-clés. Remises configurables selon quantité, fidélité, paiement comptant ou Mobile Money. Permissions proposées : `pricing.manage`, `negotiation.use`; routes tenant, jamais endpoint public donnant le plancher.

## Ports, invariants, événements

Ports : `IPriceListRepository`, `IRulesIntentReader`, `IPrivatePriceFloorReader`, `IOrderPriceWriter`, `IClock`. Le prix final approuvé est repris dans l'Order comme dernier montant accepté avant paiement, via contrat/événement distinct et compatible avec INV-OD-03. Ne pas modifier deux agrégats dans une transaction.

- `INV-PRC-01` proposition et contre-offre restent sous validation explicite du vendeur; aucune négociation/envoi automatique.
- `INV-PRC-02` prix final jamais inférieur au plancher configuré; refus sans fuite du montant plancher.
- `INV-PRC-03` devises, unité, remise, période et identité de la règle restent traçables.
- `INV-PRC-04` plancher privé absent des réponses client, exports non autorisés, métriques et logs.

Événements : `NegotiationProposalPrepared`, `SellerDecisionRecorded`, `PriceAccepted`; audit des décisions sans contenu conversationnel inutile. Tests : seuil exact, remise cumulée, fidélité/quantité/paiement Mobile Money, règle désactivée, retry, consentement vendeur et non-fuite du plancher.

## Cas limites et configuration

Prix absent, changement de liste pendant thread, taux FX périmé, quantité hors palier, devise non supportée, client demande une promesse de stock, seller declines et nouvelle contre-offre. Configurer paliers, raisons de remise, validité et intents par pack; aucune remise universelle. Extension : ajouter une règle de remise par données, vérifier l'invariant plancher et tests de non-divulgation avant activation.
