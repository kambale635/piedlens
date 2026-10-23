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
- **INV-OD-05** : Agrégation du "argent qui dort" toujours par devise homogène (`Money.add()` refuse d'additionner deux devises différentes) — jamais d'addition arithmétique nue.
- **INV-OD-06** : Pas de double planification d'un `Reminder` identique (même `orderId` + même `reminderType`) en statut `Scheduled` simultanément.
- **INV-OD-07** : Une détection dont le `confidenceScore` est inférieur au seuil configuré est persistée comme `DetectionCandidate` en `pending_review`, jamais comme `Order`. Un candidat est décidé une seule fois : `pending_review` devient `promoted` ou `rejected`, et un `Order` n'est créé qu'au moment d'une validation manuelle explicite.

## 6. Invariants — CRM

- **INV-CRM-01** : Clé d'identité d'un `Contact` = `externalIdentifier`, jamais `displayName`. Un changement de `displayName` met à jour le contact existant, ne crée jamais de doublon.
- **INV-CRM-02** : `CRMSegment` ne stocke jamais la liste de ses membres — toujours calculée dynamiquement (`SegmentMembershipCalculator`), pour éviter la désynchronisation entre agrégats.
- **INV-CRM-03** : Fusion de contacts (`MergeContactsUseCase`) uniquement déclenchable manuellement par le merchant, jamais automatique — trace d'audit obligatoire conservée après fusion.
- **INV-CRM-04** : `totalSpentByCurrency` et `orderCount` d'un `Contact` sont recalculés uniquement en réaction à `OrderStatusChanged` (statut `paid_and_delivered`), jamais modifiés directement par un autre chemin. Chaque devise est cumulée séparément selon INV-OD-05; aucune conversion implicite n'est permise.

## 7. Invariants transverses (tous contextes)

- **INV-TR-01** : Aucun agrégat modifié en dehors de sa propre transaction — jamais deux Aggregate Roots modifiés dans la même opération. Communication inter-agrégats exclusivement par événements.
- **INV-TR-02** : Toute émission d'événement de domaine passe par la table `outbox_events` du contexte producteur, dans la même transaction que la modification de l'agrégat (voir `14-event-driven-architecture.md`).
- **INV-TR-03** : Tout consommateur d'événement est idempotent — vérifie `processed_events` avant traitement, sans exception.
- **INV-TR-04** : Aucune requête ORM ne joint directement deux schémas de contextes différents, même si techniquement possible dans une base PostgreSQL unique.
- **INV-TR-05** : Tout `Money` circule toujours comme Value Object `{ amount, currency }`, jamais comme nombre nu, dans quelque contexte que ce soit.

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
