# Bounded Context : Order Detection ("argent qui dort")

## Rôle
Détecter automatiquement, à partir des messages évalués par le Rules Engine, les commandes en attente de paiement ou de livraison, et générer des relances pour que le merchant ne perde jamais d'argent par oubli.

## Use Cases

### `DetectOrderUseCase`
- **Déclencheur** : événement `MessageEvaluated` avec signal d'intention d'achat.
- **Cas score ≥ seuil** : crée directement un `Order` en `pending_payment`, publie `OrderDetected`.
- **Cas score < seuil** : crée un `DetectionCandidate` en `PendingReview` — **aucun `Order` n'est créé à ce stade** (voir INV-OD-04, INV-OD-07, et `02-domain-model.md` pour la justification de cet agrégat séparé). Publie `DetectionCandidateCreated`.
- Persister via `IOrderRepository` (cas Order) ou `IDetectionCandidateRepository` (cas candidat).

### `ValidateOrRejectDetectionUseCase`
Opère sur un `DetectionCandidate`, jamais directement sur un `Order` :
1. `validate` → crée un **nouvel** `Order` (id distinct du candidat) en `pending_payment`, marque le candidat `Promoted` avec référence vers l'`Order` créé
2. `reject` → marque le candidat `Rejected`, aucun `Order` créé
3. Dans les deux cas, publie `DetectionCorrectedByMerchant` pour l'ajustement du Rules Engine (voir `08-context-rules-engine.md`)

**Règle de corrélation (important, cas limite fréquent)** : un nouveau message concernant potentiellement une commande existante est rattaché à l'`Order` `PendingPayment` ou `PaidNotDelivered` le plus récent du même `contactId`, dans une fenêtre de X jours (configurable). Au-delà, on considère qu'il s'agit d'une nouvelle commande distincte, même du même client.

### `GetDormantMoneyDashboardUseCase`
1. Récupérer tous les `Order` en statut `PendingPayment` ou `PaidNotDelivered` du merchant, au-delà d'une ancienneté configurable
2. Agréger le montant total (`Money.add()`, jamais une addition brute de nombres — cohérence de devise garantie par le Value Object)
3. Trier par ancienneté et montant

### `ScheduleReminderUseCase`
1. Selon les règles de relance configurées par le merchant (ou règles par défaut du plan), créer un `Reminder` avec `scheduledFor` calculé
2. Persister, planifier l'exécution différée (voir `04-tech-stack-infrastructure.md` §2.5, job Redis)

### `SendScheduledRemindersUseCase`
Exécuté par le job planifié à l'heure prévue :
1. Récupérer les `Reminder` en statut `Scheduled` dont `scheduledFor` est passé
2. Générer le message personnalisé (variables remplacées)
3. Appeler `IMessageSender` (contexte Platform Connectors) pour l'envoi (ou proposer à validation manuelle si le plan du merchant ne permet pas l'envoi automatique)
4. Marquer `Processed`, publier `ReminderSent [EVT]`

## Machine à états de `Order` (rappel, voir aussi `02-domain-model.md`)

```
PendingPayment ──(PaymentDetected)──▶ PaidNotDelivered ──(DeliveryConfirmed)──▶ PaidAndDelivered
      │                                      │
      └──────────(Cancelled)─────────────────┘
```
Toute transition hors de ce graphe lève `InvalidOrderTransitionException` — implémentée **dans la méthode `changeStatus()` de l'agrégat `Order`**, jamais dans le Use Case (respect strict de l'encapsulation DDD : l'agrégat protège ses propres invariants).

## Interfaces (ports)

```
interface IOrderRepository {
  save(order: Order): void
  findById(id: OrderId): Order | null
  findPendingByContact(contactId: ContactId, withinDays: number): Order[]
  findDormant(merchantId: MerchantId, olderThanHours: number): Order[]
}

interface IReminderScheduler {
  schedule(reminder: Reminder): void
  cancel(reminderId: ReminderId): void
}
```

## Gestion de la confiance et validation manuelle (anti-frustration utilisateur)

Toute détection avec `confidenceScore` inférieur au seuil configuré (ex : 70) ne crée **jamais** d'`Order` — elle crée un `DetectionCandidate` distinct (voir `02-domain-model.md`), présenté au merchant dans une file "à valider" (`ListPendingDetectionCandidatesUseCase`). Sa validation (`ValidateOrRejectDetectionUseCase`, décision `validate`) crée alors un nouvel `Order` ; son rejet ne crée jamais rien. Dans les deux cas, l'événement `DetectionCorrectedByMerchant [EVT]` est publié, consommé par le Rules Engine pour ajustement (voir `08-context-rules-engine.md`).

## Interfaces (ports) — complément

```
interface IDetectionCandidateRepository {
  save(candidate: DetectionCandidate): void
  findById(id: DetectionCandidateId): DetectionCandidate | null
  findPendingByMerchant(merchantId: MerchantId): DetectionCandidate[]
}
```

## Cas limites à couvrir explicitement

- Négociation de prix en plusieurs messages → le montant retenu est celui du dernier message contenant un `AmountPattern` détecté avant un signal de paiement, pas le premier montant mentionné dans la conversation
- Commande annulée après détection de paiement (remboursement) → transition explicite vers `Cancelled` depuis `PaidNotDelivered`, jamais une suppression de l'`Order` (traçabilité)
- Plusieurs commandes simultanées du même client → chaque `Order` reste distincte ; la règle de corrélation par fenêtre temporelle ne doit jamais fusionner deux commandes différentes du même client si les montants ou contextes de conversation divergent clairement

## Tests attendus

- Tests de la machine à états (toutes les transitions valides ET toutes les transitions invalides rejetées)
- Test de la règle de corrélation (nouveau message → bon `Order` existant vs nouvel `Order`)
- Test du calcul du dashboard "argent qui dort" avec agrégation multi-devises correcte (si un merchant a des clients payant en devises différentes)
