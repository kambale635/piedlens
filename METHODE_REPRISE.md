Fait : sous-étape a validée, réconciliation idempotente/Outbox atomique, seed fr/en configurable, tests unitaires et ORM, docs 11/15/16 avec INV-OD-09; commit `feat(order-detection): reconcile payment and delivery messages`.
Prochaine action : committer séparément l’E2E paiements/livraison par webhooks signés, puis les scénarios faible confiance et Backup; confirmer enfin le garde-fou PostgreSQL CI.
Test : `./venv/bin/python manage.py test tests.integration.test_e2e_message_to_dormant_order --settings=config.test_settings -v 1`
