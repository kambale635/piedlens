# Bounded Context : Supplier Network (`SUP`)

## Rôle et agrégats

Aider à découvrir et évaluer des fournisseurs sans certifier une identité ni garantir une transaction. Agrégats : `SupplierProfile`, `VerificationCase` (étapes, consentement, pièces chiffrées, revue humaine), `RetailerSupplierLink` (consentement), `WholesaleCatalog` (paliers/minimum), `PurchaseOrder`, `SupplierReview`, `SupplierDispute`.

Niveaux de vérification déclarés : téléphone, identité, entreprise, références. Le statut décrit seulement les vérifications effectuées, avec date et périmètre; jamais une garantie d'honnêteté. Revue par le personnel via `supplier.verify` globale. Documents KYC classés sensibles, chiffrés, accès minimal, rétention/suppression définies par avis juridique RDC.

## Use Cases

| Use Case | Entrée → sortie | Erreurs / événements |
|---|---|---|
| `CreateSupplierProfileUseCase` | `{ ownerMerchantId, profile, consent }` → `{ supplierId, status }` | consentement absent; `SupplierProfileCreated` |
| `OpenVerificationCaseUseCase` | `{ supplierId, level, documentReferences[], consentId }` → `{ caseId, status }` | format/consentement; `VerificationCaseOpened` |
| `ReviewVerificationCaseUseCase` | `{ caseId, decision, reasonCode, reviewerId }` → `{ status, reviewedAt }` | permission `supplier.verify`, conflit; `SupplierVerificationReviewed` |
| `LinkSupplierUseCase` | `{ retailerMerchantId, supplierId, consentId }` → `{ linkId }` | refus/révocation consentement; `RetailerSupplierLinked` |
| `PublishWholesaleCatalogUseCase` | `{ supplierId, currency, tiers[], minimumOrder }` → `{ version }` | prix/devise/paliers; `WholesaleCatalogPublished` |
| `CreatePurchaseOrderUseCase` | `{ retailerMerchantId, supplierId, lines[], agreedTerms }` → `{ purchaseOrderId, status }` | minimum, disponibilité, devises; `PurchaseOrderPlaced` |
| `SubmitSupplierReviewUseCase` | `{ purchaseOrderId, rating, evidence? }` → `{ reviewId }` | commande non terminée, duplicate; `SupplierReviewSubmitted` |

Permissions proposées : `supplier.read`, `supplier.manage`, `supplier.verify` plateforme, `po.create`, `po.manage`, `po.read`. Les bons de commande sont des engagements entre parties; aucun paiement fournisseur interne sans prestataire agréé.

## Invariants, ports et événements

Ports : `ISupplierRepository`, `IVerificationDocumentStore`, `IReviewerPermissionChecker`, `IConsentReader`, `IWholesaleCatalogReader`. `INV-SUP-01` revue humaine traçable; `INV-SUP-02` lien retailer-fournisseur fondé sur consentement révocable; `INV-SUP-03` documents chiffrés et jamais dans logs; `INV-SUP-04` avis uniquement après commande terminée; `INV-SUP-05` scores expliqués par facteurs/poids configurés, sans prétendre prédire la fraude.

Cas limites : usurpation d'identité, document falsifié/expiré, entreprise homonyme, lien révoqué, litige, tentative de représailles dans avis, fournisseur non vérifié. Tests : accès reviewer, isolation merchant, chiffrement/retention, révocation, avis hors commande refusé, justification score reproductible et concurrence de revue.

Configuration : niveaux/champs requis, types de document autorisés, poids du score, délais, minimum/paliers par devise; revue juridique nécessaire. Extension : adapter preuve à pays/pack, laisser le statut « non vérifié » tant qu'une revue humaine n'est pas faite; S3/document store réel attend identifiants en doc 28.
