# Order Detection

Detects orders and payment/delivery state from evaluated messages, and tracks dormant money.

Reference: [docs/11-context-order-detection.md](../../../docs/11-context-order-detection.md).

Use Cases implemented: DetectOrderUseCase, ValidateOrRejectDetectionUseCase, CreateOrderFromPromotedDetectionUseCase, ReassignContactReferencesFromContactMergedUseCase, UpdateOrderStatusUseCase, GetDormantMoneyDashboardUseCase, ScheduleReminderUseCase, SendScheduledRemindersUseCase, and ListPendingDetectionCandidatesUseCase.

`Money` is owned by the shared kernel; do not define a duplicate in this app.

`DetectOrderUseCase` is implemented with separate `Order` and `DetectionCandidate` aggregates. Low-confidence detections never create an `Order` (INV-OD-04, INV-OD-07); producer events are appended to the transactional outbox through the injected unit of work (INV-TR-02).

`DetectOrderUseCase` deduplicates `MessageEvaluated` by `(event_id, order-detection-consumer)` and serializes detections per contact before correlation, saving the aggregate, outbox event, and processed marker together (INV-OD-02, INV-TR-01/02/03). Candidate review locks the candidate row before its one-time decision.

The dormant-money dashboard returns one `Money` total per currency, never a cross-currency sum. It includes only the merchant's `pending_payment` and `paid_not_delivered` orders older than the requested threshold (INV-OD-05).

`ScheduleReminderUseCase` resolves delays through an injected merchant/plan policy. It persists the separate Reminder aggregate and `ReminderScheduled` outbox event atomically. A partial unique constraint on scheduled `(order_id, reminder_type)` enforces INV-OD-06; the outbox relay, not the Use Case, queues Redis jobs.

`SendScheduledRemindersUseCase` claims due reminders with recoverable leases. Plan policy selects manual proposals or automatic delivery; the gateway must deduplicate by `Reminder.id`. Success/proposal and their outbox/processed-event markers commit together; failures receive a configured retry time. External delivery stays outside the database transaction.

`ListPendingDetectionCandidatesUseCase` returns a merchant-scoped, stable oldest-first page of `pending_review` candidates with the unpaginated total count. Defaults are page 1 and 50 results, with a maximum page size of 100.

`ReassignContactReferencesFromContactMergedUseCase` consumes only the IDs from CRM's `ContactMerged` event and ignores its snapshot. It locks and updates each Order and DetectionCandidate in a separate transaction, rechecks the old `contact_id`, and records the processed-event marker only after both scans finish. A failed partial run is safe to replay; already reassigned aggregates are skipped (INV-CRM-03, INV-TR-01/03/04).

ACID transactions are concretely implemented in `infrastructure/`: `DjangoOrderDetectionUnitOfWork` wraps `transaction.atomic()`, and ORM repositories, outbox, and processed-event records share the default database connection. `piedlens_platform.di.container.ApplicationContainer` is the composition root. The migration currently creates prefixed tables in PostgreSQL's default schema; native per-context schema routing remains outstanding. SQLite integration tests prove commit/rollback, while PostgreSQL CI must verify row-lock concurrency.

Tests: `PYTHONPATH=src python -m unittest discover -s tests/unit/order_detection -p 'test_*.py' -v`; Django integration tests: `python manage.py test tests.integration.order_detection --settings=config.test_settings`.