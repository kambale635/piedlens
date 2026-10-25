# Afrique : commerce social, vision et principes

## Rôle et pilote

Aider les vendeurs déjà actifs sur WhatsApp Business à transformer les conversations en ventes suivies, sans leur retirer la décision. Pilote : RDC; extension internationale par packs pays configurables. Segment initial : vendeurs sociaux digitalisés, cohérent avec le ciblage de `18-product-vision-and-objectives.md`.

| Persona | Problème à résoudre |
|---|---|
| Vendeur WhatsApp | Messages, paiements et commandes difficiles à rapprocher |
| Acheteur | Instructions de paiement/livraison claires, sans paiement à un tiers non agréé |
| Fournisseur | Demandes de gros et vérification traçables |
| Livreur | Zone, frais, statut et remise vérifiables |

## Principes de conception

- Configuration plutôt que code : pays, devise, Mobile Money, langue, format local et intention sont des données versionnées; ajouter une valeur ne requiert pas de déploiement.
- Le vendeur garde la main : l'application propose, le vendeur valide. Aucune négociation, publication ou envoi n'a lieu sans son accord explicite.
- WhatsApp : aucune automatisation non officielle, scraping ou client non officiel. À la date de rédaction, disponibilité d'une API officielle adaptée au produit **à vérifier dans la documentation Meta**. En attendant, préparer le contenu; le vendeur publie lui-même.
- Argent : la plateforme ne détient, ne transfère ni ne séquestre les fonds. Paiement ou séquestre uniquement par un prestataire agréé, après validation juridique locale.
- Confidentialité : collecte minimale, consentement et finalité visibles; données sensibles chiffrées et accès audité.

## Ce que le produit ne fait pas

- Ne garantit ni paiement, livraison, authenticité d'un fournisseur, ni rendement commercial.
- Ne négocie ni n'envoie de message de manière autonome; ne lit pas les comptes par scraping.
- Ne garde pas les fonds et ne fournit pas de service financier, KYC/AML ou juridique.
- N'impose pas de taux de change, frais, langue locale ou règle de conformité universels.

## Validation juridique requise

Avant chaque marché : juriste local pour qualification des paiements/agrégation et éventuel séquestre, KYC/AML, protection des données et transferts transfrontaliers, conservation/suppression, prospection et communications électroniques, droit de la consommation, fiscalité et statut des livreurs/fournisseurs. En RDC, confirmer aussi les licences, autorités et obligations applicables. La liste est un point de revue, pas un avis juridique.

## Modèle et cas d'usage

Agrégats de référence : `Merchant`, `CountryPack`, `ConversationImportConsent`, et les agrégats décrits par contexte dans `31`–`39`. Use Cases : voir `15-use-cases-catalog.md`, section « Contextes Afrique »; chaque document de contexte référencé fait foi pour le contrat détaillé.

| Port / événement | Contrat directeur |
|---|---|
| `ICountryPackReader`, `IPermissionChecker`, Outbox par contexte | `01`, `14`, `20` |
| `ExternalPaymentReceived` | Réutiliser l'événement existant; ne pas créer un doublon de paiement externe |
| Événements catalogue, prix, stock, négociation, fournisseur, livraison, storefront | Émis par leur contexte via Outbox et consommés idempotemment |

Invariants marché : `INV-AF-01` consentement/contrôle vendeur; `INV-AF-02` aucun envoi ou mouvement d'argent non autorisé; `INV-AF-03` configuration par CountryPack; `INV-AF-04` pas de garde de fonds; `INV-AF-05` minimisation et protection des données. Détails spécialisés : préfixes `MM`, `FX`, `CAT`, `PRC`, `SUP`, `LOG`, `STO` dans les docs référencés.

## Cas limites, tests et extension

Tester consentement retiré, doublons/rejeu, réseau ou taux absent, devise non concordante, langue non vérifiée, vendeur hors zone, montant ambigu, prestataire indisponible et signal de paiement contradictoire. Les données de test ne prouvent aucune conformité réglementaire.

Recette d'extension : ajouter une entrée de configuration versionnée; valider par opérateur local; tester parsing/format/permissions/idempotence; publier le pack; observer métriques et retours; revenir à la version précédente sans migration métier. Aucun adaptateur réel sans identifiants enregistrés dans `28-external-credentials-register.md`.
