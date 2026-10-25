# Country Packs et localisation

## Rôle et agrégat

`CountryPack` rassemble les paramètres métier/localisés d'un pays et une version publiée immuable; les éditions créent une nouvelle version. Il ne contient aucun secret ni décision juridique implicite. Packs : `cd` (RDC pilote) et `generic` (fallback prudent, jamais une source de vérité réglementaire).

| Champ | RDC (`cd`, à valider) | `generic` |
|---|---|---|
| Devises | USD, CDF; afficher sans conversion implicite | Devises activées explicitement par merchant |
| Mobile Money | M-Pesa, Airtel Money, Orange Money, Afrimoney **à valider** | Aucun réseau par défaut |
| Langues UI/contenu | fr, en, sw, ln; sw/ln à valider par locuteurs natifs | fr/en comme langues de secours configurées |
| Téléphone | Indicatif, longueur et normalisation à valider avec règles RDC versionnées; garder saisie originale | E.164 seulement si validation configurée; sinon format inconnu |
| Adresse | commune, quartier, avenue, point de repère | Champs d'adresse fournis par le pack |
| Intentions et modèles | références versionnées aux règles Rules Engine; aucune phrase lingala/swahili inventée | aucune intention métier implicite |

Aucun seed linguistique swahili/lingala n'est proposé dans cette spécification : les modèles correspondants restent absents ou désactivés jusqu'à revue par des locuteurs natifs.

## Use Cases (contrat détaillé de ce contexte)

| Use Case | Entrée → sortie | Erreurs / événements |
|---|---|---|
| `PublishCountryPackUseCase` | `{ packCode, version, config, actorId }` → `{ version, status }` | `400 INVALID_PACK`, `409 VERSION_CONFLICT`; `CountryPackPublished` |
| `ResolveCountryPackUseCase` | `{ merchantId, countryCode }` → `{ packCode, version, configuration }` | fallback `generic` explicite; `CountryPackResolved` interne, non publié |
| `ValidateCountryPackUseCase` | `{ packCode, version }` → `{ valid, issues[] }` | erreurs par champ, aucune activation partielle |

`CountryPack` est l'unique agrégat modifié par publication; configuration utilisée par un autre contexte via `ICountryPackReader` ou événement de version publiée. Permissions proposées : `country_pack.manage` plateforme, `country_pack.read` merchant.

## Ports, invariants et événements

Ports : `ICountryPackRepository`, `ICountryPackReader`, `ILocaleFormatter`, `IPhoneNumberNormalizer`, `IPackApprovalPolicy`. Événement versionné `CountryPackPublished { packCode, version, checksum, publishedAt, approvedBy }`; Outbox atomique, consommateurs idempotents.

- `INV-CP-01` : données locales et règles de validation proviennent d'une version publiée, jamais d'un branchement pays codé en dur.
- `INV-CP-02` : valeurs non vérifiées restent marquées « à valider » et ne sont pas présentées comme garanties.
- `INV-CP-03` : absence de champ/config requise bloque l'opération concernée avec une erreur explicite; pas de fallback silencieux de devise ou réseau.

Cas limites : pack inconnu, merchant sans pays, version retirée, changements de format, données historiques et langue sans traduction. Tests : validation schéma, résolution versionnée, fallback `generic`, absence de conversion, règles téléphone, non-activation d'une entrée non approuvée.

## Recette d'extension

Ajouter un fichier/dataset versionné, renseigner monnaies, langues, adresse, formats, réseaux disponibles et références de règles; faire revue locale et juridique; tests de contrat; publier via `PublishCountryPackUseCase`; activer pour un petit cohort; pouvoir revenir au pack antérieur. RDC : Afrimoney et formats locaux attendent validation; traductions sw/ln obligatoirement relues par locuteurs natifs.
