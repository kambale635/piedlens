# Invariants métier & Règles — Document consolidé (source unique de vérité)

> Ce fichier rassemble en un seul endroit **tous** les invariants et règles métier disséminés dans les fichiers de contexte, pour qu'aucune règle ne soit jamais oubliée ou contredite entre deux modules. En cas de divergence apparente entre ce fichier et un fichier de contexte, **ce fichier fait foi** — les fichiers de contexte doivent être corrigés pour s'aligner.

## 1. Invariants — Identity & Access

- **INV-ID-01** : Un `Merchant` ne peut pas dépasser le nombre de `PlatformConnection` actives autorisées par son plan.
  - Starter = 1, Pro = 3, Agency = illimité
- **INV-ID-02** : `phoneNumber` est unique globalement (contrainte d'unicité en base, pas seulement applicative)
- **INV-ID-03** : Un downgrade de plan est refusé si l'usage actuel dépasse la limite du plan cible (ex : 3 connexions actives, tentative de passage à Starter qui n'en autorise qu'1) → `422 DOWNGRADE_EXCEEDS_CURRENT_USAGE`

## 2. Invariants — Platform Connectors

- **INV-PC-01** : `accessToken` n'est jamais stocké ou manipulé en clair en dehors de la couche infrastructure — le domaine ne connaît que `EncryptedToken`.
- **INV-PC-02** : Un webhook entrant sans signature valide est rejeté systématiquement (`401`), jamais traité même partiellement.
- **INV-PC-03** : Idempotence des messages — un `externalMessageId` déjà traité ne crée jamais un second `Message` (contrainte d'unicité DB sur `(platformConnectionId, externalMessageId)`).
- **INV-PC-04** : Un échec de synchronisation sur une `PlatformConnection` n'affecte jamais le traitement des autres connexions du même merchant ou d'autres merchants (isolation stricte des erreurs).

## 3. Invariants — Rules Engine

- **INV-RE-01** : Résolution de `RuleSet` par priorité stricte : règles `merchant` > règles `country` > règles `global`. Une règle plus spécifique surcharge toujours une règle plus générale du même type.
- **INV-RE-02** : `ConfidenceScore` est toujours borné [0, 100] — toute tentative de construction hors limite lève une exception à la construction du Value Object, jamais un clamp silencieux.
- **INV-RE-03** : Un ajustement de poids de règle suite à une correction manuelle (`AdjustRuleWeightFromCorrectionUseCase`) est borné à ±10 points par correction, pour éviter l'instabilité du système suite à une série de corrections contradictoires.
- **INV-RE-04** : Aucune chaîne de langue, devise, ou motif de détection n'est codée en dur dans le domaine ou l'application — toute donnée de ce type provient exclusivement de `RuleConfig` en base.

## 4. Invariants — Backup

- **INV-BK-01** : Un `BackupSnapshot` marqué `Succeeded` est immuable — jamais modifié après coup, uniquement remplacé par un nouveau snapshot.
- **INV-BK-02** : Un snapshot partiellement échoué (coupure en cours de traitement) est marqué `Failed` intégralement — jamais de snapshot partiel marqué `Succeeded`.
- **INV-BK-03** : Consentement explicite du merchant (`consentGivenAt` renseigné) obligatoire avant toute sauvegarde de données clients.
- **INV-BK-04** : `DeleteAllMerchantDataUseCase` nécessite une double confirmation (`confirmationToken`) — action irréversible, jamais déclenchable en un seul appel.

## 5. Invariants — Order Detection

- **INV-OD-01** : Machine à états stricte pour `Order.status` :
  ```
  pending_payment → paid_not_delivered → paid_and_delivered
  pending_payment → cancelled
  paid_not_delivered → cancelled
  ```
  Toute transition hors de ce graphe lève `InvalidOrderTransitionException`, levée **dans l'agrégat lui-même**, jamais dans un Use Case.
- **INV-OD-02** : Corrélation d'un nouveau signal avec une commande existante : uniquement si même `contactId` ET dans une fenêtre temporelle configurable (défaut 3 jours). Au-delà, nouvelle commande distincte, même client.
- **INV-OD-03** : Le montant retenu pour un `Order` est celui détecté dans le **dernier** message contenant un `AmountPattern` avant le signal de paiement — jamais le premier montant mentionné (cas de négociation).
- **INV-OD-04** : Détection automatique de commande uniquement si `confidenceScore >= seuil configuré` (défaut 70) ; en dessous, file de validation manuelle obligatoire, jamais de création automatique silencieuse.
- **INV-OD-05** : Agrégation de l'« argent qui dort » toujours par devise homogène (`Money.add()` refuse l'addition de devises différentes). Conversion d'affichage permise uniquement par un `RateSnapshot` explicite et conservé; le total source reste inchangé.
- **INV-OD-06** : Pas de double planification d'un `Reminder` identique (même `orderId` + même `reminderType`) en statut `Scheduled` simultanément.
- **INV-OD-07** : Une détection dont le `confidenceScore` est inférieur au seuil configuré est persistée comme `DetectionCandidate` en `pending_review`, jamais comme `Order`. Un candidat est décidé une seule fois : `pending_review` devient `promoted` ou `rejected`, et un `Order` n'est créé qu'au moment d'une validation manuelle explicite.
- **INV-OD-09** : un intent de paiement/livraison configuré dans le Rules Engine peut faire évoluer uniquement le dernier `Order` compatible du même merchant/contact dans la fenêtre de corrélation avant l'horodatage source. Le paiement suit `pending_payment → paid_not_delivered`; la livraison suit `paid_not_delivered → paid_and_delivered`. La transition est validée par `Order.change_status()`, ne crée jamais d'Order et est atomique avec le marqueur idempotent et `OrderStatusChanged` dans l'Outbox.

## 6. Invariants — CRM

- **INV-CRM-01** : Clé d'identité d'un `Contact` = `externalIdentifier`, jamais `displayName`. Un changement de `displayName` met à jour le contact existant, ne crée jamais de doublon.
- **INV-CRM-02** : `CRMSegment` ne stocke jamais la liste de ses membres — toujours calculée dynamiquement (`SegmentMembershipCalculator`), pour éviter la désynchronisation entre agrégats.
- **INV-CRM-03** : Fusion de contacts (`MergeContactsUseCase`) uniquement déclenchable manuellement par le merchant, jamais automatique — trace d'audit obligatoire conservée après fusion.
- **INV-CRM-04** : `totalSpentByCurrency` et `orderCount` d'un `Contact` sont recalculés uniquement en réaction à `OrderStatusChanged` (statut `paid_and_delivered`), jamais modifiés directement par un autre chemin. Chaque devise est cumulée séparément selon INV-OD-05; aucune conversion implicite n'est permise.
- **INV-CRM-08** : un segment comparant `totalSpent` doit déclarer sa devise. Dépenses, prix, marge et seuils restent dans leur devise; comparer ou afficher une autre devise exige un `RateSnapshot` explicite associé à la vue/transaction. Une conversion ne remplace jamais la valeur source ni son historique.

## 7. Invariants transverses (tous contextes)

- **INV-TR-01** : Aucun agrégat modifié en dehors de sa propre transaction — jamais deux Aggregate Roots modifiés dans la même opération. Communication inter-agrégats exclusivement par événements.
- **INV-TR-02** : Toute émission d'événement de domaine passe par la table `outbox_events` du contexte producteur, dans la même transaction que la modification de l'agrégat (voir `14-event-driven-architecture.md`).
- **INV-TR-03** : Tout consommateur d'événement est idempotent — vérifie `processed_events` avant traitement, sans exception.
- **INV-TR-04** : Aucune requête ORM ne joint directement deux schémas de contextes différents, même si techniquement possible dans une base PostgreSQL unique.
- **INV-TR-05** : Tout montant circule comme `Money { amount, currency }`, jamais comme nombre nu. Une conversion est permise uniquement via un `RateSnapshot` explicite contenant paire, taux, source, date d'effet et règle d'arrondi; le snapshot accompagne la transaction convertie.

## 7A. Invariants — Commerce social Afrique

- **INV-AF-01** : configuration pays/langue/devise/réseau/intention en données versionnées; aucun branchement pays codé en dur.
- **INV-AF-02** : aucune négociation, publication, envoi ou action de paiement sans décision explicite du vendeur.
- **INV-AF-03** : aucun fonds détenu par la plateforme; mouvements réels uniquement par un prestataire agréé.
- **INV-AF-04** : collecte minimisée, consentement/finalité enregistrés, données sensibles protégées et supprimables selon politique validée.

## 7B. Invariants — Contextes Afrique

- **INV-PAY-01** : montant minor-unit et devise d'une `PaymentAttempt` sont immuables; tout webhook discordant place la tentative en `needs_review` sans effet financier.
- **INV-PAY-02** : un seul effet par identifiant d'événement fournisseur et un seul succès par payable; le second succès devient `duplicate_payment` et émet une demande de remboursement.
- **INV-PAY-03** : une preuve `unverified` (SMS/capture) ne confirme jamais un paiement; seul `seller_confirmed` ou `provider_confirmed` peut faire avancer l'état.
- **INV-PAY-04** : aucun fonds détenu par la plateforme; reversement uniquement vers un `SettlementAccount` vérifié.
- **INV-PAY-05** : les frais sont calculés et enregistrés lors de la création de la tentative, sans recalcul au webhook.
- **INV-PAY-06** : machine `created -> pending -> succeeded|failed|expired|cancelled`, puis `succeeded -> partially_refunded|refunded`; événements tardifs/hors ordre ne régressent pas l'état; webhook après expiration => `needs_review`; les attentes anciennes sont rapprochées par job.
- **INV-PAY-07** : paiement partiel interdit en V1; seul le montant exact est confirmé, sinon `needs_review`.

 
 **INV-PAY-01** : `PaymentAttempt.amountMinor` et `currency` sont immuables; un webhook qui diverge place la tentative en `needs_review` et ne produit aucun effet financier.
 **INV-PAY-02** : un seul effet par événement fournisseur et un seul paiement réussi par payable; tout second succès est `duplicate_payment` et demande un remboursement.
 **INV-PAY-03** : les preuves `unverified` (SMS/capture) ne confirment jamais un paiement; seules les confirmations explicites vendeur ou fournisseur peuvent avancer l'état.
 **INV-PAY-04** : la plateforme ne détient pas les fonds; les reversements ne peuvent viser qu'un `SettlementAccount` vérifié.
 **INV-PAY-05** : les frais sont calculés et stockés à la création de l'Attempt; ils ne sont jamais recalculés au traitement d'un webhook.
 **INV-PAY-06** : états `created -> pending -> succeeded|failed|expired|cancelled`, `succeeded -> partially_refunded|refunded`; webhook tardif après expiration => `needs_review`; les événements hors ordre ne font pas reculer l'état; les `pending` anciens sont rapprochés par job.
 **INV-PAY-07** : paiement partiel interdit en V1; montant exact ou `needs_review`.
 **Machine d'état `PaymentAttempt`** : `created -> pending -> succeeded|failed|expired|cancelled`; `succeeded -> partially_refunded|refunded`; les états terminaux n'acceptent aucun événement ancien hors compensation explicite.
- **Machine d'état `ConversationImport`** : `queued -> processing -> completed|completed_with_errors|failed`; `processing -> queued` après échec transitoire; une transition terminale ne revient pas à `processing`. Les erreurs par ligne sont conservées sans contenu sensible.
- **INV-CP-01..03** : CountryPack publié/versionné; données non validées restent signalées; absence de configuration requise bloque l'opération.
- **INV-MM-01..05** : preuve distincte d'un paiement confirmé; identifiant de transaction dédupliqué; montant/devise rapprochés; pas de custodie; écritures et marqueurs idempotents.
- **INV-FX-01..04** : taux positif versionné; snapshot immuable; arrondi configurable; dépassement de seuil alerte sans changer automatiquement le prix.
- **INV-CAT-01..04** : mouvements de stock append-only; limites négatives explicites; prix/unité/devise traçables; fichiers/photos protégés.
- **INV-PRC-01..04** : vendeur approuve; contre-offre jamais sous plancher; prix versionné; plancher privé jamais exposé ni journalisé.
- **INV-SUP-01..05** : vérification humaine traçable, consentement révocable, documents protégés, avis après commande terminée, score explicable.
- **INV-LOG-01..04** : frais configurés, transitions autorisées, code de remise protégé/limité, COD rapproché sans détention des fonds.
- **INV-STO-01..04** : publication Status manuelle, vitrine publique sans données privées, prix versionné sans plancher, attribution révocable sans PII.
- **INV-WA-01..04** : import consenti/minimisé/supprimable; aucune automatisation non officielle; compte non éligible redirigé vers le parcours manuel.

## 8. Limites par plan et économie configurable

Les valeurs effectives sont stockées dans Billing et lues par les autres contextes exclusivement via `IEntitlementReader`. Les valeurs Discovery, Starter, Pro et Agency sont le seed provisoire documenté dans `src/contexts/billing/README.md`; elles sont modifiables par `plan.manage`, ne sont pas des constantes métier, et `-1` signifie illimité. L'export reste autorisé sur tous les plans.

- **INV-PLAN-01** : aucun contexte consommateur ne lit les tables Billing directement; tout droit est lu via `IEntitlementReader`. Un droit manquant ou quota atteint retourne `402 PLAN_UPGRADE_REQUIRED` avec la clé d'entitlement.
- **INV-PLAN-02** : l'export des données est autorisé sur tous les plans et `export_enabled` ne peut être désactivé.
- **INV-BILL-01** : un merchant ne peut commencer qu'un essai; son expiration rétablit les droits du plan courant sans suppression ni perte des données merchant.
- **INV-BILL-02** : un même coupon ne peut être consommé qu'une fois par merchant; limites, usage, redemption et événement sont atomiques dans Billing.
- **INV-BILL-03** : la récompense referral est accordée au seul premier paiement du filleul, une fois; pas d'auto-parrainage et limite par parrain configurable.
- **INV-BILL-04** : `manual_link` ne fait aucun appel API et ne consomme aucun quota. `api_send` réserve idempotemment son quota mensuel par destinataire; dépassement retourne `422 OUTBOUND_CAP_REACHED`.
- **INV-BILL-05** : les tarifs outbound sont configurés par pays, catégorie, devise et validité; aucune conversion automatique. L'estimation est indicative, Meta facture directement le vendeur et jamais Billing.
- **INV-BILL-06** : un `api_send` sans tarif actif correspondant au pays/catégorie/devise est refusé avec `422 OUTBOUND_RATE_MISSING` avant toute réservation de quota. Le rapport mensuel peut exclure les catégories non tarifées de son total uniquement s'il fournit `unpricedMessageCount` et `estimateIncomplete=true`; jamais de zéro silencieux.

## 9. Règles de sécurité et conformité (rappel consolidé)

- Chiffrement au repos de tout token d'accès plateforme (AES-256 minimum)
- Aucun contenu de message client en clair dans les logs applicatifs
- Droit à l'oubli implémenté dès le MVP, pas reporté en V2
- Consentement explicite tracé avant toute collecte/sauvegarde de données clients d'un merchant

## 10. Invariants — Access Control (rôles & permissions)

- **INV-AC-01** : aucune vérification d'accès dans le code applicatif/présentation autrement que via `IPermissionChecker.can()` — zéro comparaison de rôle en dur.
- **INV-AC-02** : un utilisateur ne peut jamais accorder (`AssignRoleToUserUseCase`) un rôle dont les permissions dépassent celles qu'il possède lui-même sur le même scope (anti auto-élévation).
- **INV-AC-03** : toute action sur les données d'un merchant vérifie le scope (`AccessScope`) EN PLUS de la permission — un `Staff` du merchant A ne peut jamais agir sur le merchant B même avec la bonne permission nommée.
- **INV-AC-04** : toute création/modification/révocation de rôle ou d'assignation est tracée (`grantedBy`, horodatage) — jamais d'action silencieuse sur les droits d'accès.
- **INV-AC-05** : le cache de vérification de permission a un TTL court (secondes) et est invalidé immédiatement sur tout changement de rôle/assignation.

## 11. Invariants — Gestion des erreurs

- **INV-ERR-01** : le domaine ne lève que des `DomainException`, jamais une exception technique brute (voir `22-error-handling-and-exceptions.md`).
- **INV-ERR-02** : une exception non prévue (500) ne renvoie jamais de stack trace ni de détail technique au client — uniquement `errorCode` et `correlationId`.
- **INV-ERR-03** : chaque `DomainException` cite l'identifiant `INV-XX-NN` de l'invariant qu'elle protège dans son docstring.
