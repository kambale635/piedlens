# Bounded Context : Logistics (`LOG`)

## Rôle et agrégats

Décrire la livraison, ses frais et ses preuves de remise sans être un transporteur ni un portefeuille. Agrégats : `DeliveryZone` (limites, frais/devise, exclusions), `CourierProfile`, `Delivery` (Order, itinéraire, états, code de remise hashé), `TransportAgencyShipment` (référence saisie manuellement).

## Use Cases

| Use Case | Entrée → sortie | Erreurs / événements |
|---|---|---|
| `QuoteDeliveryUseCase` | `{ merchantId, address, package, currency }` → `{ zoneId, fee: Money, estimateExpiry }` | hors zone, adresse incomplète, devise non supportée |
| `AssignCourierUseCase` | `{ deliveryId, courierId }` → `{ status }` | courier indisponible, scope; `CourierAssigned` |
| `UpdateDeliveryStatusUseCase` | `{ deliveryId, status, actorId, evidence? }` → `{ status, updatedAt }` | transition/permission invalide; `DeliveryStatusChanged` |
| `ConfirmHandoverUseCase` | `{ deliveryId, code }` → `{ handedOverAt }` | code expiré/invalide, tentatives dépassées; `DeliveryHandedOver` |
| `RegisterAgencyShipmentUseCase` | `{ orderId, agencyCode, manualReference, fee? }` → `{ shipmentId }` | référence absente/doublon; `AgencyShipmentRegistered` |
| `ReconcileCashOnDeliveryUseCase` | `{ deliveryId, collectedAmount, currency, payoutReference }` → `{ outcome }` | mismatch, doublon; `CashOnDeliveryReconciled` |

Permissions proposées : `delivery.manage` merchant, `delivery.update` livreur; scope de livreur limité à ses affectations. Routes proposées : `/api/v1/deliveries`, `/api/v1/deliveries/{id}/status`, `/api/v1/deliveries/{id}/handover`.

## Ports, invariants et événements

Ports : `IDeliveryRepository`, `IDeliveryFeeConfigReader`, `ICourierAssignmentPolicy`, `IPayoutReconciliationReader`, `ICodeHasher`. `INV-LOG-01` frais/zones proviennent du pack ou configuration merchant versionnée; `INV-LOG-02` changement d'état autorisé par machine à états; `INV-LOG-03` code à 4 chiffres généré aléatoirement, stocké haché, expirant et soumis à limite d'essais; `INV-LOG-04` paiement à la livraison est collecté par livreur puis rapproché par référence, jamais détenu par l'app.

COD : remise au livreur/documentation de reversement fait l'objet d'un rapprochement, pas d'un transfert par PiedLens. Une agence de transport utilise référence et état saisis manuellement jusqu'à adaptateur autorisé. Événements via Outbox : `CourierAssigned`, `DeliveryStatusChanged`, `DeliveryHandedOver`, `CashOnDeliveryReconciled`; consommateurs idempotents.

Cas limites/tests : zone frontalière, frais modifiés après devis, colis retourné, code brute-force/réutilisé, montant COD incomplet, reversement partiel, agence sans API, changement d'Order concurrent. Tester isolation, idempotence, limites de tentatives, immutabilité du devis et rapprochement.

Configuration/extension : polygones ou listes de quartiers, frais, durée code, transitions, livreurs et agences par pack. Ajouter une zone par données; adaptateur agence seulement si officiel, autorisé et credentials référencés.
