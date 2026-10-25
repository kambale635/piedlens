# Bounded Context : Currency Rates (`FX`)

## Rôle et agrégats

Gérer les taux du vendeur et des snapshots de conversion auditables. Agrégats : `MerchantRate` (merchant, paire source/cible, valeur décimale positive, source, date d'effet, période, auteur) et `RateSnapshot` (taux figé, source/version/instant, précision et arrondi appliqué). Historique append-only; modifier un taux ajoute une version.

## Use Cases

| Use Case | Entrée → sortie | Erreurs / événements |
|---|---|---|
| `SetMerchantRateUseCase` | `{ merchantId, baseCurrency, quoteCurrency, rate, source, effectiveAt }` → `{ rateId, version }` | paire invalide, valeur non positive; `MerchantRateSet` |
| `GetEffectiveRateUseCase` | `{ merchantId, pair, at }` → `{ rate, source, effectiveAt }` | `RATE_NOT_CONFIGURED`; lecture seule |
| `CreateRateSnapshotUseCase` | `{ transactionId, pair, at }` → `{ snapshotId, rate, roundedAmount }` | rate absent ou périmé selon politique; `RateSnapshotCreated` |
| `ReviewRateChangeUseCase` | `{ merchantId, pair }` → `{ changePercent, threshold, priceReviewRequired }` | taux insuffisant; `RateChangeThresholdExceeded` |
| `DisplayDualCurrencyUseCase` | `{ Money, targetCurrency, snapshotId? }` → `{ source, converted?, snapshot? }` | sans snapshot, affiche une seule devise |

Permission proposée : `fx.manage`; API `PUT /api/v1/fx/rates` et `GET /api/v1/fx/rates?pair=...` avec route tenant protégée. `IRateSource` est optionnel pour une source de référence; jamais obligatoire ni source de prix merchant sans consentement.

## Invariants

- `INV-FX-01` taux positif, paire explicite, date d'effet et source conservés; historique immuable.
- `INV-FX-02` toute conversion liée à une transaction stocke son `RateSnapshot`; le taux courant ne réécrit jamais l'historique.
- `INV-FX-03` arrondi/précision sont des paramètres du CurrencyPack; pas d'arrondi universel implicite.
- `INV-FX-04` dépassement de seuil configuré déclenche une alerte de revue de prix, jamais un changement de prix automatique.
- `INV-CRM-08` (nouvel identifiant) : dépenses, prix, segments et marge restent dans leur devise; conversion seulement avec `RateSnapshot` explicite.
- `INV-OD-05` amendé : agrégation « argent qui dort » par devise; conversion d'affichage permise uniquement par snapshot explicite, jamais dans le total source.
- `INV-TR-05` amendé : tout montant circule comme `Money`; conversion explicite transporte également le `RateSnapshot` associé.

Événements : `MerchantRateSet`, `RateSnapshotCreated`, `RateChangeThresholdExceeded`; Outbox FX et marqueur idempotent côté consommateur. Tests : paire inversée/absente, taux effectif historique, changement de taux sans altérer snapshot, règles d'arrondi, seuil et devise de segment.

## Cas limites et configuration

Taux absent, stale, source externe indisponible, taux révisé rétroactivement, grande précision, devise sans fraction, paire inversée et taux nul/négatif. Merchant configure source manuelle par défaut; source référence et seuil d'alerte restent désactivés/configurables jusqu'à validation. Extension : ajouter codes de devises, précision/arrondi au pack; enregistrer une source via `IRateSource`; tests de snapshots avant activation.
