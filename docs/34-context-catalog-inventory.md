# Bounded Context : Catalog & Inventory (`CAT`)

## Rôle et agrégats

Catalogue de vente et quantités disponibles. Agrégats : `Product` (merchant, libellés localisés, photos/références), `ProductVariant` (SKU/options, `Money` par devise, unité), `StockLedger` (mouvements append-only) et `StockAlertPolicy`. Unité : pièce, carton, lot, kg; conversion d'unités uniquement par facteur configuré et historisé.

## Use Cases

| Use Case | Entrée → sortie | Erreurs / événements |
|---|---|---|
| `CreateProductUseCase` | `{ merchantId, localizedNames, variants[] }` → `{ productId }` | devise/unité invalide; `ProductCreated` |
| `UpdateProductUseCase` | `{ merchantId, productId, patch, version }` → `{ version }` | non trouvé, conflit de version; `ProductUpdated` |
| `AdjustStockUseCase` | `{ merchantId, variantId, quantity, unit, reason, idempotencyKey }` → `{ movementId, balance }` | quantité invalide, unité incompatible; `StockAdjusted` |
| `ImportCatalogCsvUseCase` | `{ merchantId, fileReference, mapping, dryRun }` → `{ accepted, rejected[] }` | format, limite, permission; `CatalogImportCompleted` |
| `GetLowStockAlertsUseCase` | `{ merchantId }` → `{ alerts[] }` | aucune écriture; `LowStockDetected` éventuellement |
| `AttachProductPhotoUseCase` | `{ productId, consentId, uploadReference }` → `{ photoId }` | MIME/taille, stockage absent; `ProductPhotoAttached` |

Permissions proposées : `catalog.read`, `catalog.manage`, `stock.adjust`, `catalog.import`. Routes tenant : `/api/v1/catalog/products`, `/api/v1/catalog/imports`, `/api/v1/catalog/variants/{id}/stock-adjustments`.

## Ports, invariants, événements

Ports : `IProductRepository`, `IStockLedgerRepository`, `ICsvReader`, `IPhotoStorage` (S3 optionnel), `IUnitConversionConfig`. `INV-CAT-01` toute correction de stock produit un mouvement append-only; `INV-CAT-02` commande réservée ne vend pas une quantité négative, sauf politique explicite; `INV-CAT-03` prix porte une devise et une unité; `INV-CAT-04` photos/CSV respectent consentement, minimisation et chiffrement requis.

Événements : `ProductCreated/Updated`, `StockAdjusted`, `LowStockDetected`, `CatalogImportCompleted`; publication Outbox atomique, consumers idempotents. Aucun événement `Order` n'est publié par CAT; la conversion entre agrégats est asynchrone.

## Cas limites et tests

SKU dupliqué par merchant, variantes supprimées référencées par Order, retour/stock négatif, carton/pièce, import partiellement invalide, CSV malformé/injection de formule, photo trop volumineuse et rollback d'un lot. Tests : isolation tenant, ledger non modifiable, idempotence import/adjust, validations devise/unité, seuil de stock et photo chiffrée.

Configuration par pack : unités, catégories, seuils d'alerte, taille/type photo, modèle CSV; aucun assortiment ou prix RDC codé dans le domaine. Extension : ajouter une unité/catégorie par configuration; nouvelle capacité de stockage derrière port; adaptateur S3 seulement après identifiants doc 28.
