# Vision Produit & Objectifs — Document de référence unique

> Ce fichier est le point d'entrée business du projet. Il consolide tous les objectifs exprimés depuis le tout début de la réflexion produit, pour que personne (humain ou IA) n'ait besoin de retrouver une conversation passée pour comprendre pourquoi le système existe.

## 1. Le problème et le marché cible

Cible : personnes déjà actives et digital-native en Afrique (et potentiellement au-delà) — créateurs de contenu, vendeurs Instagram/WhatsApp Business, freelances (Upwork/Fiverr), community managers/agences, gamers/streamers monétisés. Point commun : usage quotidien intensif des réseaux, déjà habitués à payer des outils numériques, revenu dépendant de plateformes qu'ils ne contrôlent pas.

**Explicitement écarté** : les commerçants "traditionnels" peu digitalisés — ce n'est pas la cible (décision prise explicitement en cours de réflexion, à ne pas réintroduire sans nouvelle validation produit).

## 2. Exigences produit non négociables (fixées dès le départ)

- **Non-optionnel** : l'outil doit toucher à l'argent que l'utilisateur reçoit, paie, ou risque de perdre — jamais un outil "de confort" qu'on désinstalle après la nouveauté.
- **Prix très bas, valeur perçue élevée** : 1 à 5 $/mois, jamais un outil qui semble cher malgré sa valeur.
- **Coût d'exploitation maîtrisé** : éviter les architectures qui dépendent d'appels IA coûteux à chaque interaction — préférer logique de règles + API externes low-cost (voir `13-technology-decision-adr.md` et `08-context-rules-engine.md`).
- **Effet "wow" démontrable en vidéo courte (TikTok/Meta)** : chaque fonctionnalité doit pouvoir se montrer en quelques secondes avec un avant/après convaincant.
- **Adaptabilité totale, zéro élément codé en dur** : doit fonctionner pour n'importe quel pays, langue, devise, plateforme, sans réécriture de code — traduit en architecture par le Rules Engine configurable (`08-context-rules-engine.md`).

## 3. Les 5 couches produit (roadmap complète, MVP + V2)

| Couche | Nom | Statut | Référence technique |
|---|---|---|---|
| 1 | Radar produits gagnants (tendances mondiales, quoi vendre) | V2 — reporté après traction du MVP | non modélisé techniquement pour l'instant, volontairement (coût d'agrégation externe élevé) |
| 2 | Sauvegarde automatique anti-ban | **MVP** | `10-context-backup.md` |
| 3 | Argent qui dort (détection commandes/paiements non finalisés) | **MVP** | `11-context-order-detection.md` |
| 4 | Mini-CRM automatique | **MVP** | `12-context-crm.md` |
| 5 | Alerte anti-arnaque (faux paiements/reçus) | V2 — s'appuiera sur le Rules Engine existant (nouveau `RuleType`) | à modéliser en V2, extension naturelle de `08-context-rules-engine.md` |

**Pourquoi cet ordre et ce découpage MVP/V2** : les couches 2, 3, 4 s'appuient sur les mêmes données déjà captées (messages, contacts) et se construisent l'une sur l'autre sans dépendance externe lourde. Les couches 1 et 5 demandent soit une agrégation de données externes coûteuse (couche 1), soit un raffinement du moteur de règles avec plus de recul terrain (couche 5) — les reporter n'est pas un renoncement, c'est une séquence délibérée pour sortir vite.

## 4. Les 4 émotions/leviers de rétention (stratégie produit, pas juste technique)

| Couche | Émotion visée | Pourquoi ça retient l'utilisateur |
|---|---|---|
| Sauvegarde | Peur (protection) | Filet de sécurité qu'on ne désinstalle jamais |
| Argent qui dort | Cupidité/opportunité | "Cet outil m'a remboursé 10 fois son prix" — moteur du bouche-à-oreille |
| Mini-CRM | Confort/gain de temps | Devient une habitude quotidienne |
| Anti-arnaque (V2) | Peur (sécurité transactionnelle) | Renforce la confiance sur la durée |

Un outil qui ne joue que sur un seul de ces leviers se désinstalle dès que l'émotion s'apaise — c'est pourquoi le produit combine plusieurs couches dès le MVP.

## 5. Modèle économique

| Plan | Prix | Contenu |
|---|---|---|
| Starter | 1-2 $/mois | Sauvegarde quotidienne + tableau argent qui dort basique, 1 compte connecté |
| Pro | 4-5 $/mois | Temps réel, relances automatiques, CRM complet, multi-comptes |
| Agence | 10-15 $/mois | Multi-clients, exports illimités, segments avancés |

## 6. Indicateurs de succès

- Taux de rétention à 30 jours (indicateur prioritaire pour un outil censé être "non-optionnel")
- Montant moyen d'argent qui dort détecté par utilisateur/semaine (preuve de valeur, exploitable en marketing)
- Taux de conversion des relances automatiques envoyées
- Taux de faux positifs de détection (à surveiller en continu — un faux positif répété détruit la confiance)

## 7. Documents associés — où trouver quoi

| Besoin | Fichier |
|---|---|
| Spécification fonctionnelle complète des couches MVP | `19-cahier-des-charges-fonctionnel.md` |
| Architecture technique stratégique | `01-architecture-overview.md` |
| Modèle de domaine (agrégats, VO, événements) | `02-domain-model.md` |
| Tous les invariants et règles métier consolidés | `16-business-invariants-and-rules.md` |
| Catalogue complet des cas d'usage avec paramètres | `15-use-cases-catalog.md` |
| Décision technologique (langage, base de données) | `13-technology-decision-adr.md` |
| Architecture événementielle | `14-event-driven-architecture.md` |
| Standards de documentation/commentaires | `17-documentation-standards.md` |
| Instructions strictes pour GitHub Copilot | `06-copilot-instructions.md` |
