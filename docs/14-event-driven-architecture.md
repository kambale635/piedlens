# Architecture événementielle — Redis Streams, publisher par contexte, fiabilité

Ce fichier comble un manque du premier jet : le mécanisme d'événements n'était que mentionné, pas spécifié. Voici la version complète.

## 1. Principe : chaque contexte a SON `IEventPublisher`, mais une seule implémentation technique partagée

Tu as raison de vouloir qu'"chaque application ait son publisher complet" — mais attention à un piège : ça ne veut pas dire réécrire un client Redis différent dans chaque module Django. Ça veut dire que **chaque contexte définit sa propre interface** (respect DIP), toutes implémentées par **une seule classe d'infrastructure partagée** (`RedisStreamEventPublisher`), injectée différemment selon le contexte pour écrire sur son propre flux.

```python
# domain/ports.py — dans CHAQUE contexte, sa propre interface (même si le contrat est identique)
class IEventPublisher(Protocol):
    def publish(self, event: DomainEvent) -> None: ...

# platform/event_bus/redis_stream_publisher.py — UNE SEULE implémentation technique
class RedisStreamEventPublisher:
    def __init__(self, redis_client, stream_name: str):
        self._redis = redis_client
        self._stream_name = stream_name  # ex: "order-detection.events"

    def publish(self, event: DomainEvent) -> None:
        self._redis.xadd(self._stream_name, event.to_envelope())
```

Chaque contexte est injecté (composition root, voir `05-module-structure.md`) avec une instance pointant vers **son propre stream Redis nommé** : `platform-connectors.events`, `rules-engine.events`, `backup.events`, `order-detection.events`, `crm.events`. Ça donne l'isolation que tu veux (chaque app "a" son publisher, au sens où elle en possède une instance configurée pour elle), sans dupliquer le code technique.

## 2. Un stream par contexte producteur, des consumer groups par contexte consommateur

```
Stream: platform-connectors.events
  └── event: MessageReceived
        Consumer Group: rules-engine-consumer   (lit et évalue)
        Consumer Group: backup-consumer          (lit et sauvegarde)

Stream: rules-engine.events
  └── event: MessageEvaluated
        Consumer Group: order-detection-consumer
        Consumer Group: crm-consumer

Stream: order-detection.events
  └── event: OrderStatusChanged
        Consumer Group: crm-consumer
        Consumer Group: notification-consumer

Stream: crm.events
  └── event: RelationshipAnomalyDetected
        Consumer Group: notification-consumer
  └── event: ContactMerged
        Consumer Group: crm-contact-merge-consumer  (absorbe l'instantané sur le Contact principal)
        Consumer Group: order-detection-contact-merge-consumer  (réattribue les références localement)
```

`ContactMerged` porte l'instantané CRM figé lors du tombstone du doublon. Chaque consumer ne modifie que ses propres agrégats. Order Detection réattribue chaque `Order` et chaque `DetectionCandidate` dans des transactions distinctes; ses écritures sont idempotentes et reprenables avant l'inscription du marqueur de complétion. Le CRM ne consulte jamais les tables Order Detection.

**Pourquoi des Consumer Groups (`XREADGROUP`) et pas du simple Pub/Sub Redis ?** Le Pub/Sub classique perd les messages si le consommateur est hors ligne au moment de la publication — inacceptable ici (un événement `PaymentDetected` manqué = argent perdu pour le merchant). Les Consumer Groups de Redis Streams garantissent la relecture (`XREADGROUP` + `XACK`), avec possibilité de rejouer les événements non acquittés (`XPENDING` / `XCLAIM`) en cas de crash d'un worker.

## 3. Le problème du "dual write" — et sa solution : Outbox Pattern

**Le piège classique à éviter absolument** : si ton code fait `db.save(order)` puis `redis.publish(event)` en deux étapes séparées, un crash entre les deux crée une incohérence silencieuse (l'`Order` existe en base mais personne n'est jamais notifié — l'argent qui dort ne sera jamais détecté par le CRM).

**Solution : Transactional Outbox Pattern.**
1. Dans la **même transaction PostgreSQL** que la sauvegarde de l'agrégat, on insère aussi l'événement dans une table `outbox_events` du contexte concerné.
2. Un processus séparé (`OutboxRelayWorker`, un par contexte, tournant en tâche de fond Django — Celery beat ou simple worker) lit `outbox_events`, publie vers Redis Streams, puis marque la ligne comme publiée.
3. Ça garantit qu'un événement est **toujours** publié si et seulement si la transaction métier a réussi — atomicité garantie par la transaction PostgreSQL, pas par une promesse de code.

```python
# application/detect_order_use_case.py
def execute(self, ...):
    with transaction.atomic():
        order = Order.create(...)
        self._order_repo.save(order)
        self._outbox_repo.add(OrderDetected.from_order(order))  # même transaction
    # Le OutboxRelayWorker se charge de la publication réelle vers Redis, séparément
```

## 4. Schéma d'enveloppe d'événement (identique pour tous les contextes — contrat partagé)

```json
{
  "eventId": "uuid",
  "eventType": "OrderDetected",
  "eventVersion": 1,
  "occurredAt": "2026-09-27T10:00:00Z",
  "producedBy": "order-detection",
  "correlationId": "uuid (pour tracer une chaîne d'événements liés)",
  "payload": { }
}
```

`eventVersion` dès le départ — indispensable pour faire évoluer le format d'un événement plus tard sans casser les consommateurs existants (un consommateur peut gérer plusieurs versions en parallèle pendant une transition).

## 5. Idempotence côté consommateur (obligatoire)

Chaque consommateur doit être capable de recevoir deux fois le même événement sans effet de bord dupliqué (Redis Streams garantit "au moins une fois", pas "exactement une fois"). Solution : table `processed_events (event_id, consumer_name)` avec contrainte d'unicité, vérifiée avant traitement — pattern simple, systématique, à appliquer dans **tous** les consommateurs sans exception.

## 6. Ce que ça donne concrètement dans `06-copilot-instructions.md` (règle à ajouter)

> 11. **Jamais de publication d'événement hors transaction** : toute émission d'événement de domaine passe par l'Outbox (table `outbox_events` du contexte), jamais un appel direct à Redis depuis un Use Case. Le `OutboxRelayWorker` est le seul composant autorisé à publier réellement vers Redis Streams.
> 12. **Idempotence obligatoire** : tout consommateur d'événement vérifie `processed_events` avant traitement — sans exception, même pour un événement jugé "peu critique".

## 7. Récapitulatif du flux complet, bout en bout (exemple réel)

```
1. Webhook WhatsApp reçu → HandleIncomingWebhookUseCase (platform-connectors)
2. Transaction : save Message + insert outbox_events(MessageReceived)
3. OutboxRelayWorker (platform-connectors) → publie sur stream "platform-connectors.events"
4. rules-engine-consumer lit l'événement → EvaluateMessageUseCase
5. Transaction : save EvaluationResult + insert outbox_events(MessageEvaluated)
6. OutboxRelayWorker (rules-engine) → publie sur stream "rules-engine.events"
7. order-detection-consumer lit → DetectOrderUseCase → Order créé
8. Transaction : save Order + insert outbox_events(OrderDetected)
9. OutboxRelayWorker (order-detection) → publie sur stream "order-detection.events"
10. crm-consumer lit → UpdateContactFromOrderUseCase → Contact mis à jour
```

Chaque flèche est fiable (outbox), traçable (`correlationId`), et rejouable en cas de panne (Consumer Groups). C'est ce qui rend le système robuste sans complexité de microservices distribués.

## Implémentation ACID du contexte Order Detection

Dans ce projet, les Use Cases dépendent de ports `IOrderDetectionUnitOfWork` et `IOrderDetectionOutbox`. Les implémentations concrètes sont dans `src/contexts/order_detection/infrastructure/` : `DjangoOrderDetectionUnitOfWork` utilise `transaction.atomic()`, et les repositories Django, l'outbox et `processed_events` écrivent sur la même connexion PostgreSQL `default`. Le composition root `src/piedlens_platform/di/container.py` injecte ces adapters; aucun Use Case ne crée d'objet infrastructure.

La transaction englobe toutes les écritures SQL concernées : agrégat, outbox et marqueur idempotent. Une exception avant la sortie du bloc annule toutes ces écritures. Le consumer verrouille aussi une ligne `CandidateOrderCreationLockRecord` via `select_for_update()` et une contrainte unique sur `Order.source_candidate_id` protège les republications.

La migration actuelle crée des tables préfixées `order_detection_*` dans le schéma PostgreSQL par défaut. L'ADR demande un schéma natif par bounded context; cette isolation de schéma n'est pas encore configurée et devra être ajoutée avec le routage/migrations PostgreSQL avant de revendiquer cette exigence comme satisfaite. Elle est indépendante de l'atomicité, qui reste assurée tant que les écritures restent sur la même base/connexion.

Les tests d'intégration avec SQLite vérifient commit, rollback et idempotence, mais SQLite n'applique pas réellement `SELECT FOR UPDATE`. Un contrôle de concurrence PostgreSQL en CI reste obligatoire avant production.
