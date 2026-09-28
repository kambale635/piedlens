# Cahier des Charges — Outil de Protection & Croissance pour Vendeurs Digitaux

## Version 1.0 — Scope MVP : Couches Sauvegarde / Argent qui dort / Mini-CRM

---

## 1. Vision du produit

Un outil unique qui s'installe une fois et devient invisible dans le quotidien d'un vendeur/créateur actif sur les réseaux sociaux (WhatsApp Business, Instagram, Facebook, TikTok). Il protège son activité, lui fait gagner de l'argent qu'il perdait sans le savoir, et automatise la gestion de ses clients — sans qu'il ait à changer ses habitudes de travail.

**Principe fondateur : rien n'est codé en dur.** Chaque comportement (détection de paiement, langue, devise, type de plateforme, règles de relance) doit être piloté par configuration, pas par du code spécifique à un cas. C'est ce qui permet à l'outil de s'adapter à n'importe quel pays, langue, plateforme, devise, sans réécriture.

---

## 2. Personas cibles

| Persona | Comportement | Douleur principale |
|---|---|---|
| Vendeuse Instagram/WhatsApp (mode, cosmétiques) | 50-300 DM/jour, vend en photos/stories | Perd des ventes dans le flot de messages |
| Freelance (design, montage, dev) | Facture via WhatsApp/Payoneer | Pas de vue d'ensemble de ses revenus |
| Petit e-commerçant TikTok Shop / dropshipping | Gère plusieurs comptes réseaux | Peur du bannissement, perte de l'historique client |
| Community manager / agence | Gère les comptes de 3-10 clients | A besoin d'une vue consolidée multi-comptes |

Point commun : actifs quotidiennement, déjà habitués à payer des outils numériques, revenu dépendant de plateformes tierces qu'ils ne contrôlent pas.

---

## 3. Architecture générale — principe d'adaptabilité

### 3.1 Modèle en couches indépendantes

```
┌─────────────────────────────────────────────┐
│         COUCHE PRÉSENTATION (App/Web)        │
├─────────────────────────────────────────────┤
│   MOTEUR DE RÈGLES CONFIGURABLE (le cœur)    │
│  - Règles de détection (multilingue)         │
│  - Règles de relance                         │
│  - Règles de scoring client                  │
├─────────────────────────────────────────────┤
│         CONNECTEURS DE PLATEFORMES            │
│  WhatsApp Business API │ Meta Graph API       │
│  (chacun = un module interchangeable)         │
├─────────────────────────────────────────────┤
│      BASE DE DONNÉES UNIFIÉE (agnostique)     │
└─────────────────────────────────────────────┘
```

**Pourquoi cette architecture ?** Ajouter une nouvelle plateforme (ex. TikTok Shop demain) = écrire un nouveau connecteur, sans toucher au moteur de règles ni à la base de données. Ajouter une nouvelle langue ou devise = ajouter une entrée de configuration, sans toucher au code.

### 3.2 Le moteur de règles configurable (la pièce maîtresse)

Au lieu de coder "si le message contient 'payé' alors marquer comme payé" (ce qui ne marche qu'en français), on construit :

- Une **table de mots-clés par langue/pays**, éditable sans redéploiement (français, anglais, arabe, wolof, lingala, pidgin, etc.)
- Une **table de devises et formats de montants** (F CFA, Naira, Cedi, Dirham, Shilling, avec leurs formats d'écriture : "5000F", "₦5,000", "5.000 FCFA")
- Une **table de motifs de reconnaissance** (regex/patterns) pour identifier : un montant, un nom de client, une confirmation de paiement, une capture d'écran de reçu
- Un **système de scoring pondéré**, où chaque signal (mot-clé, emoji ✅, capture d'écran) ajoute des points, et un seuil configurable déclenche l'action

Ceci est la différence entre un outil "codé en dur" et un outil qui s'adapte à tout pays/langue sans réécriture.

---

## 4. Modélisation des données

### 4.1 Entités principales

**User** (le vendeur, propriétaire du compte)
- id, nom, téléphone, pays, langue préférée, devise, plan d'abonnement, date d'inscription

**PlatformConnection** (un compte connecté)
- id, user_id, type_plateforme (whatsapp/instagram/facebook), identifiant_externe, token_accès (chiffré), statut_connexion, date_dernière_sync

**Contact** (un client du vendeur — généré automatiquement, jamais saisi manuellement)
- id, user_id, platform_connection_id, nom_affiché, identifiant_externe, date_première_interaction, date_dernière_interaction, montant_total_acheté (calculé), nombre_commandes (calculé), score_fidélité (calculé), tags (auto + manuels)

**Message** (copie sauvegardée, brute et horodatée)
- id, contact_id, platform_connection_id, contenu_texte, contenu_media_url, type (texte/image/audio), sens (entrant/sortant), horodatage, hash_intégrité

**Order** (commande détectée automatiquement à partir des messages)
- id, contact_id, montant_détecté, devise, statut (en_attente_paiement / payé_non_livré / payé_livré / annulé), date_détection, date_dernier_changement_statut, messages_source (référence), confiance_détection (score 0-100)

**PaymentSignal** (preuve détectée d'un paiement)
- id, order_id, type_signal (mot-clé/capture_écran/emoji), contenu_source, date_détection, score_confiance

**Reminder** (relance générée automatiquement)
- id, order_id, type (paiement_en_attente/livraison_en_attente), statut (à_envoyer/envoyée/traitée), date_prévue, canal

**BackupSnapshot** (sauvegarde quotidienne)
- id, user_id, platform_connection_id, date_snapshot, taille_données, statut (réussi/échoué), lien_export

**CRMSegment** (regroupement automatique de contacts)
- id, user_id, nom_segment (ex : "clients VIP", "inactifs 30j"), critère_définition (règle configurable), contacts_membres (calculé dynamiquement)

**RuleConfig** (le cœur du moteur adaptable)
- id, portée (globale/pays/user), type_règle (mot_clé/devise/seuil_scoring), clé, valeur, langue, actif

### 4.2 Relations

```
User 1─N PlatformConnection 1─N Contact 1─N Message
Contact 1─N Order 1─N PaymentSignal
Order 1─N Reminder
User 1─N BackupSnapshot
User 1─N CRMSegment N─N Contact
```

---

## 5. Spécifications fonctionnelles détaillées

## COUCHE 2 — Sauvegarde automatique (protection anti-ban)

### 5.1 Objectif
Garantir que même si le compte du vendeur est suspendu, supprimé ou piraté, aucune donnée client n'est perdue.

### 5.2 Fonctionnalités

**F2.1 — Synchronisation continue**
- Récupération automatique de tous les nouveaux messages/contacts toutes les X minutes (configurable selon le plan tarifaire : temps réel pour plan premium, toutes les heures pour plan basique)
- Stockage chiffré, horodaté, avec hash d'intégrité pour prouver qu'aucune donnée n'a été altérée après coup (utile en cas de litige)

**F2.2 — Sauvegarde des médias**
- Images de produits, captures d'écran de paiement, messages vocaux — stockés séparément avec référence dans le message d'origine
- Compression intelligente pour limiter les coûts de stockage sans perdre l'information utile

**F2.3 — Restauration rapide**
- En cas de bannissement : export complet en un clic (format lisible + format ré-importable)
- Génération automatique d'une liste de contacts avec leur historique d'achat, exportable en CSV/PDF, pour permettre une reprise de contact manuelle immédiate sur un nouveau compte

**F2.4 — Alerte de santé de compte**
- Détection de signaux avant-coureurs (baisse brutale de messages entrants, message d'avertissement de la plateforme détecté dans les notifications système si accessible) → alerte préventive au vendeur

**F2.5 — Multi-comptes**
- Un même vendeur peut connecter plusieurs comptes (WhatsApp + Instagram + comptes secondaires) et voir une sauvegarde unifiée ou séparée selon préférence

### 5.3 Cas limites à couvrir
- Que faire si la plateforme change son API et coupe l'accès ? → Connecteur doit avoir un mode dégradé (dernière sauvegarde connue reste accessible)
- Que faire si le vendeur change de numéro de téléphone ? → Procédure de migration de compte sans perte de sauvegarde
- Conformité : le vendeur doit donner un consentement explicite pour la sauvegarde des données de SES clients (RGPD-like, même hors UE, par bonne pratique)

---

## COUCHE 3 — Argent qui dort (détection de commandes non finalisées)

### 5.4 Objectif
Détecter automatiquement, à partir des messages, l'argent que le vendeur devrait recevoir ou livrer mais qui reste en attente — et le relancer avant qu'il ne l'oublie.

### 5.5 Fonctionnalités

**F3.1 — Détection automatique de commande**
- Le moteur de règles scanne chaque nouveau message entrant/sortant à la recherche de motifs : montant + intention d'achat ("je veux", "combien pour", "je prends")
- Création automatique d'un objet Order en statut "en_attente_paiement" dès qu'un signal suffisant est détecté (score de confiance ≥ seuil configurable)

**F3.2 — Détection automatique de paiement**
- Reconnaissance de mots-clés multilingues ("payé", "envoyé", "c'est fait", "paid", "sent"), d'émojis (✅💰), et surtout de captures d'écran de confirmation Mobile Money/bancaire (traitement d'image basique : détection de la présence d'une capture d'écran dans la conversation au bon moment, pas nécessairement OCR complet au MVP)
- Changement automatique du statut de la commande vers "payé_non_livré"

**F3.3 — Détection de livraison**
- Mots-clés de confirmation de livraison ("reçu", "bien arrivé", "livré", "delivered") → statut "payé_livré", commande clôturée

**F3.4 — Tableau de bord "argent qui dort"**
- Vue quotidienne : liste des commandes en_attente_paiement depuis plus de X heures, avec montant total agrégé affiché en gros ("340 000 F en attente")
- Tri par ancienneté, par montant, par client

**F3.5 — Relances automatiques configurables**
- Le vendeur définit une fois ses règles ("relancer après 24h de silence", "message de relance : ...") et le système propose (ou envoie automatiquement, selon plan) un message de relance pré-rempli et personnalisable
- Journal des relances envoyées pour éviter les doublons agaçants

**F3.6 — Score de confiance et validation manuelle**
- Chaque commande détectée affiche son score de confiance ; en dessous d'un seuil, elle apparaît dans une file "à valider manuellement" pour éviter les faux positifs qui agaceraient l'utilisateur
- Chaque correction manuelle du vendeur réentraîne/ajuste les règles pour ce compte (apprentissage simple, pas nécessairement du ML lourd au MVP — un ajustement de poids suffit)

### 5.6 Cas limites à couvrir
- Négociation de prix en plusieurs messages → le montant final doit être le dernier mentionné, pas le premier
- Commande annulée après paiement détecté → prévoir un statut "annulé" et ne pas la compter dans l'argent qui dort
- Plusieurs commandes du même client en parallèle → chaque Order doit être distincte, pas fusionnée

---

## COUCHE 4 — Mini-CRM automatique

### 5.7 Objectif
Construire, sans aucune saisie manuelle, une fiche client exploitable pour fidéliser et relancer en masse.

### 5.8 Fonctionnalités

**F4.1 — Fiche client automatique**
- Générée et mise à jour en continu : nom, historique de commandes, montant total dépensé, fréquence d'achat, dernière interaction, préférences détectées (produits mentionnés le plus souvent)

**F4.2 — Segmentation automatique**
- Segments pré-configurés modifiables : "Clients VIP" (montant total > seuil configurable), "Inactifs" (pas d'achat depuis X jours), "Nouveaux" (première interaction < 7 jours), "Réguliers" (fréquence élevée)
- Le vendeur peut créer ses propres segments avec des règles simples (interface "si... alors...", pas de code)

**F4.3 — Messages groupés**
- Sélection d'un segment → envoi d'un message personnalisé (avec variables : {prénom}, {dernier_produit}) à tous les membres, dans les limites autorisées par chaque plateforme (respect des règles anti-spam WhatsApp/Meta)

**F4.4 — Rappels de relation**
- Alerte "Ça fait 45 jours que {client} n'a rien acheté, il/elle achetait en moyenne tous les 30 jours" — détection d'anomalie simple sur la fréquence habituelle du client

**F4.5 — Export et interopérabilité**
- Export de la base clients en CSV à tout moment (le vendeur reste propriétaire de sa donnée, argument de confiance fort)

### 5.9 Cas limites à couvrir
- Un même client peut écrire depuis plusieurs numéros/comptes → prévoir une fusion manuelle de fiches en doublon
- Changement de nom d'affichage du client sur la plateforme → ne pas créer un nouveau contact, s'appuyer sur l'identifiant technique stable, pas le nom affiché

---

## 6. Parcours utilisateur (flow principal)

1. Inscription → choix du pays/langue/devise (pré-remplit le moteur de règles)
2. Connexion d'un ou plusieurs comptes (WhatsApp Business, Instagram)
3. Consentement explicite pour la sauvegarde et l'analyse des messages
4. Synchronisation initiale (import de l'historique existant si l'API le permet)
5. Écran d'accueil : résumé du jour ("X commandes en attente, Y F qui dorment, Z messages non répondus")
6. Notifications quotidiennes proactives (push/WhatsApp) résumant l'essentiel sans besoin d'ouvrir l'app
7. Actions rapides en un clic : relancer, exporter, segmenter

---

## 7. Exigences non-fonctionnelles

- **Faible bande passante** : l'app doit fonctionner correctement en 3G, avec synchronisation différée et compression des médias — contrainte critique en contexte africain
- **Multilingue dès le départ** : structure de configuration en base, pas de texte codé en dur dans l'interface
- **Sécurité** : chiffrement des tokens d'accès aux plateformes, chiffrement des messages stockés, jamais de mot de passe en clair
- **Confidentialité** : le vendeur doit pouvoir supprimer toutes ses données et celles de ses clients à tout moment (droit à l'oubli)
- **Scalabilité** : architecture connecteurs/moteur de règles pensée pour ajouter de nouvelles plateformes sans refonte
- **Disponibilité** : la sauvegarde ne doit jamais dépendre uniquement d'un service tiers gratuit — prévoir redondance de stockage

---

## 8. Intégrations techniques nécessaires

| Besoin | Option | Remarque coût |
|---|---|---|
| Lecture messages WhatsApp | WhatsApp Business API (Meta) | Facturation par conversation, prévoir dans le pricing |
| Lecture messages Instagram/Facebook | Meta Graph API (Messaging) | Gratuit dans les limites de l'API officielle |
| Détection de texte dans capture d'écran | OCR léger (Tesseract open-source) | Pas besoin d'IA lourde/payante au MVP |
| Envoi de notifications | Push notification + WhatsApp template messages | Coût par message, à répercuter dans le prix |
| Stockage médias | Stockage objet standard (type S3-compatible) | Coût proportionnel au volume, compresser les médias |

**Point d'attention majeur** : l'accès officiel à l'API WhatsApp Business et à l'API Meta nécessite une validation par Meta (numéro professionnel vérifié). Le prévoir dans le planning, ce n'est pas instantané.

---

## 9. Modèle économique (aligné sur la demande : prix très bas, valeur perçue élevée)

| Plan | Prix indicatif | Contenu |
|---|---|---|
| Starter | 1-2 $/mois | Sauvegarde quotidienne + tableau "argent qui dort" basique, 1 compte connecté |
| Pro | 4-5 $/mois | Temps réel, relances automatiques, mini-CRM complet, multi-comptes |
| Agence | 10-15 $/mois | Multi-clients, exports illimités, segments avancés |

---

## 10. Roadmap suggérée

**MVP (couches 2, 3, 4 — ce document)**
- 1 plateforme au départ (WhatsApp Business, la plus utilisée) pour valider vite
- Moteur de règles avec 2-3 langues/devises au lancement, architecture prête pour en ajouter facilement

**V2**
- Ajout Instagram/Facebook
- Couche 5 (radar produits gagnants)
- Couche anti-arnaque

---

## 11. Indicateurs de succès (KPIs) à suivre dès le lancement

- Taux de rétention à 30 jours (l'indicateur le plus important pour un outil "non-optionnel")
- Montant moyen d'"argent qui dort" détecté par utilisateur et par semaine (preuve de valeur concrète, à utiliser dans le marketing)
- Nombre de relances envoyées via l'app et taux de conversion de ces relances
- Taux de faux positifs sur la détection de paiement (à surveiller de près, sinon perte de confiance rapide)
