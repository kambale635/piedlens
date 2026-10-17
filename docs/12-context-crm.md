# Bounded Context : CRM (mini-CRM automatique)

## Rôle
Construire et maintenir automatiquement une fiche client exploitable, sans aucune saisie manuelle, à partir des événements des autres contextes.

## Use Cases

### `UpdateContactFromMessageUseCase`
Déclenché en réaction à `MessageReceived [EVT]`.
1. Résoudre le `Contact` existant via `externalIdentifier` (jamais via `displayName`, voir invariant `02-domain-model.md`) ou en créer un nouveau si première interaction
2. Mettre à jour `lastInteractionAt`
3. Si le `displayName` a changé côté plateforme, le mettre à jour sans créer de doublon

### `UpdateContactFromOrderUseCase`
Déclenché en réaction à `OrderStatusChanged [EVT]` (émis par le contexte Order Detection — communication inter-contexte par événement, jamais par appel direct entre repositories).
1. Si le nouveau statut est `PaidAndDelivered` : recalculer `totalSpent` (via `Money.add()`) et `orderCount` du `Contact` concerné
2. Invoquer `LoyaltyScoreCalculator` (domain service) pour recalculer `loyaltyScore`
3. Ajouter au `purchaseHistory` CRM l'`orderId` et `updatedAt` de l'événement; une commande déjà présente n'est pas comptée deux fois, même si elle arrive avec un autre `eventId`
4. Sauvegarder le `Contact` et le marqueur `processed_events` dans la même transaction (INV-TR-03)

L'historique de dates est prospectif à partir du déploiement de cette fonctionnalité. Les Contacts existants ne sont pas rétroactivement enrichis en lisant Order Detection; leur `orderCount` historique ne fournit pas de dates d'achat.

### `CalculateSegmentMembersUseCase`
1. Pour un `CRMSegment` donné, invoquer `SegmentMembershipCalculator.evaluate(segment.definitionRule, contacts)`
2. Résultat mis en cache Redis (TTL configurable, 5 minutes par défaut) et invalidé après commit d'une modification de Contact — jamais stocké de façon permanente sur l'agrégat `CRMSegment` (évite désynchronisation, cf. frontière d'agrégat DDD).
3. `total_spent` est toujours comparé comme `Money` dans sa devise déclarée, sans addition ni conversion d'autres devises. L'opérateur `contains` ne s'applique qu'aux tags et compare des valeurs exactes.

### `SendBulkMessageUseCase`
1. Résoudre les membres du segment (`GetSegmentMembersUseCase`) et figer l'audience dans la campagne.
2. Persister la campagne et ses journaux de destinataires, puis `BulkMessageQueued` dans l'Outbox CRM, dans une seule transaction.
3. Retourner immédiatement `{ bulkMessageLogId, status: processing, recipientCount }`; aucune API de plateforme n'est appelée dans la requête.

Le texte `template` reçu est déjà rendu. Le CRM ne substitue pas `{prenom}` ou `{dernier_produit}` : aucune source fiable de prénom/dernier produit n'est définie dans ses agrégats; ces variables sont reportées jusqu'à définition d'un contrat de données.

### `ProcessBulkMessageCampaignUseCase`
Le consumer CRM traite les journaux de destinataires un par un; chaque état destinataire est persisté séparément pour garder les transactions courtes. `IRateLimiter` peut laisser un destinataire en attente pour reprise. `IMessageSender` reçoit la clé stable `campaignId:contactId` et doit dédupliquer les retries; l'appel externe reste hors transaction SQL. À la fin seulement, le worker marque la campagne `completed`, ajoute `BulkMessageCompleted` à l'Outbox et marque `(eventId, crm-bulk-message-consumer)` dans la même transaction. Aucun contenu de message n'est stocké dans le journal de livraison.

### `DetectRelationshipAnomalyUseCase`
Job planifié périodique. Règle d'anomalie (voir INV-CRM-05, INV-CRM-06) :
1. **Historique suffisant** : le contact a au moins `min_purchases` achats (`paid_and_delivered`), défaut 3. Sinon il est ignoré (pas assez de données pour dire ce qui est "habituel").
2. **Intervalle habituel** : médiane des intervalles entre achats consécutifs (la médiane résiste mieux aux achats exceptionnels que la moyenne).
3. **Inactivité actuelle** : nombre de jours depuis le dernier achat.
4. **Anomalie** si `inactivité > intervalle_habituel × anomaly_multiplier` (défaut 2.0) ET `inactivité >= min_inactivity_days` (défaut 7, plancher anti-bruit pour les clients quasi quotidiens).
5. **Une seule alerte par période de silence** : une fois `RelationshipAnomalyDetected` émis pour un contact, aucune nouvelle alerte tant qu'il n'a pas racheté.
6. Publication via **Outbox CRM**, dans la même transaction que l'enregistrement de la notification (voir INV-TR-02).

La période est identifiée par `(contactId, lastPurchaseOrderId)` dans le registre de notifications CRM; la contrainte unique en base protège également les exécutions concurrentes. Un nouveau `orderId` livré ouvre une nouvelle période.

Les paramètres `min_purchases`, `anomaly_multiplier`, `min_inactivity_days` viennent d'une configuration (défauts en settings, surcharge par merchant possible), jamais de littéraux dans le domaine (INV-RE-04). `min_purchases` doit permettre de calculer au moins un intervalle entre deux achats. Les dates d'achat viennent d'un historique d'achats **propre au CRM**, alimenté par le consommateur d'`OrderStatusChanged` — jamais par une requête vers les tables d'`order-detection` (INV-TR-04).

## Domain Services

### `LoyaltyScoreCalculator`
Calcule un score 0-100 à partir de : fréquence d'achat, récence, montant total, régularité. Règle de calcul isolée dans ce service, testable indépendamment, ajustable sans toucher à l'entité `Contact` elle-même (SRP).

### `SegmentMembershipCalculator`
Évalue une `SegmentRule` déclarative (ex : `{ field: "totalSpent", operator: ">", value: 50000 }`) contre chaque `Contact`. Conçu en Strategy Pattern pour supporter facilement de nouveaux opérateurs/champs sans modifier le calculateur existant (OCP).

## Interfaces (ports)

```
interface IContactRepository {
  save(contact: Contact): void
  findByExternalIdentifier(id: string, platformConnectionId: PlatformConnectionId): Contact | null
  findByMerchant(merchantId: MerchantId): Contact[]
}

interface ISegmentRepository {
  save(segment: CRMSegment): void
  findByMerchant(merchantId: MerchantId): CRMSegment[]
}
```

### Contrat transactionnel de `MergeContactsUseCase`

Le temps 1 verrouille et modifie uniquement le Contact doublon. `ContactMerged` contient `eventId`, `merchantId`, `primaryContactId`, `mergedContactId` et l'instantané métier du doublon. Le tombstone et l'événement CRM Outbox sont écrits atomiquement (INV-CRM-03/07, INV-TR-01/02).

Le temps 2 est traité par le consommateur CRM de `ContactMerged`; il vérifie `processed_events`, verrouille et modifie uniquement le Contact principal, absorbe une seule fois les montants du snapshot par devise via `Money.add()`, ajoute `orderCount` du snapshot à celui du principal et unit historique d'achats et tags, puis marque l'événement traité dans la même transaction (INV-CRM-04, INV-TR-01/03). Les valeurs absorbées proviennent du snapshot immuable capturé au temps 1; le doublon reste conservé pour résolution d'identité et audit.

Order Detection consomme le même événement indépendamment. Il réattribue chaque `Order` et chaque `DetectionCandidate` dans des transactions séparées, une racine par transaction. Chaque réattribution est idempotente et reprenable après crash; le consommateur n'inscrit son marqueur de complétion qu'après le traitement de toutes les racines concernées. CRM ne lit ni ne modifie les tables Order Detection.

## Cas limites à couvrir explicitement

- **Un même client écrit depuis plusieurs numéros/comptes** → pas de fusion automatique (risque d'erreur); `MergeContactsUseCase` est déclenché manuellement par le merchant et respecte INV-TR-01 en deux temps :
  1. Dans une transaction qui ne modifie que le Contact doublon, vérifier le déclenchement manuel, le même merchant, deux IDs distincts et que ni le principal ni le doublon n'est déjà fusionné. Marquer le doublon `Merged`, renseigner `mergedIntoContactId` et publier `ContactMerged` dans l'Outbox CRM avec un instantané immuable du doublon (`totalSpentByCurrency`, `orderCount`, `purchaseHistory`, `tags`), le tout dans cette transaction.
  2. Dès le commit du temps 1, conserver le doublon comme tombstone d'audit et rediriger ses identifiants externes vers le principal. Un consommateur idempotent de `ContactMerged` absorbe ensuite l'instantané dans le Contact principal dans une transaction distincte : sommes via `Money.add()` par devise, union des dates d'achat et fusion des tags; le marqueur `processed_events` est écrit dans cette transaction.
  La cohérence finale est éventuelle, de l'ordre de quelques secondes; le résultat synchrone n'inclut pas le nombre de commandes Order Detection mises à jour.
- **Changement de `displayName`** → jamais de nouveau `Contact` créé, uniquement mise à jour du champ, la clé d'identité reste `externalIdentifier`
- **Suppression de compte par un client** (droit à l'oubli du client final, pas du merchant) → prévoir un Use Case dédié qui anonymise le `Contact` (garde les agrégats statistiques nécessaires au merchant type `totalSpent` sur des segments, mais supprime les données personnelles identifiantes) plutôt qu'une suppression totale qui casserait l'intégrité des `Order` liés

## Tests attendus

- Test de non-duplication de `Contact` lors d'un changement de `displayName`
- Test du calcul de `loyaltyScore` avec plusieurs profils types (client fidèle régulier, client ponctuel gros montant, client nouveau)
- Test de `SegmentMembershipCalculator` avec règles combinées (ET/OU) si supporté dès le MVP, sinon documenter explicitement la limitation V1 (règles simples uniquement, combinaisons en V2)
