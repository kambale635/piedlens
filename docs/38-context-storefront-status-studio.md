# Bounded Context : Storefront & Status Studio (`STO`)

## Rôle et agrégats

Préparer des cartes produit et une mini-boutique publique en lecture seule; publication WhatsApp Status réalisée par le vendeur. Agrégats : `ProductCard` (référence produit, prix/devise, texte localisé, média, version) et `StorefrontPublication` (slug public, visibilité, carte publiée). N'exposer aucune donnée personnelle, plancher privé, identifiant privé ou conversation.

## Use Cases

| Use Case | Entrée → sortie | Erreurs / événements |
|---|---|---|
| `PrepareProductCardUseCase` | `{ merchantId, productId, language, templateId }` → `{ cardId, caption, mediaReference, trackingCode, waLink }` | produit/langue/media absents; `ProductCardPrepared` |
| `ApproveProductCardUseCase` | `{ merchantId, cardId, version, decision }` → `{ status }` | version périmée; `ProductCardApproved/Rejected` |
| `MarkStatusPublishedUseCase` | `{ merchantId, cardId, publishedAt }` → `{ status }` | non approuvé; `StatusPublicationRecorded` |
| `SchedulePublicationReminderUseCase` | `{ merchantId, cardId, reminderAt }` → `{ reminderId, scheduledAt }` | carte retirée/doublon; `PublicationReminderScheduled` |
| `ResolveTrackingCodeUseCase` | `{ code, receivedMessageId }` → `{ cardId? }` | code expiré/inconnu; `StatusAttributionRecorded` |
| `PublishReadOnlyStorefrontUseCase` | `{ merchantId, slug, productCardIds[] }` → `{ publicUrl, version }` | slug conflictuel, carte retirée; `StorefrontPublished` |
| `GetPublicStorefrontUseCase` | `{ slug }` → `{ merchantDisplayName?, cards[] }` | masqué/inexistant; réponse publique minimale |

Permissions proposées : `storefront.manage` tenant et `storefront.read` public limité aux cartes publiées. Le lien `wa.me` embarque le code de suivi de la carte; un message entrant portant ce code peut être attribué au Status correspondant. Le lien n'envoie rien automatiquement; le vendeur répond et publie manuellement.

## Ports, invariants, événements

Ports : `IProductCardRepository`, `IProductCatalogReader`, `ICaptionRenderer`, `ITrackingCodeGenerator`, `IPublicMediaReader`. `INV-STO-01` publication Status exige approbation explicite du vendeur et n'appelle aucune API non officielle; `INV-STO-02` storefront public en lecture seule et sans données personnelles; `INV-STO-03` prix affiché a devise/version et ne révèle jamais le plancher négociation; `INV-STO-04` code attribution aléatoire, expirant, révocable et sans contenu personnel.

Tests : validation vendeur, état non publié, fuite données sensibles, consentement photo, code périmé/dupliqué, store masqué, XSS/HTML, langues non validées, URL de tracking erronée. Cas limites : produit retiré, stock épuisé, changement prix après carte, partage de lien, publication jamais confirmée.

Configuration : modèles de légende, langues validées, durée code, thème pack; le vendeur édite avant approbation. Extension : ajouter un template ou pack culturel en données, revue native, tests de rendu et confidentialité. Automatisation de publication absente tant que voie officielle et conformité ne sont pas vérifiées et documentées.
