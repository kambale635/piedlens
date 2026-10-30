Fait : P2a validée : PaymentAttempt, prix serveur, Idempotency-Key, webhook mock signé/anti-rejeu, garde-fou production; ciblés 24/24, migrations synchronisées.
Prochaine action : commit P2a par chemins explicites; poursuivre P2b avec consumer Identity idempotent et compensation vers `needs_review`.
Test P2b : `./venv/bin/python manage.py test tests.unit.payments.test_consume_payment_succeeded_use_case tests.integration.payments --settings=config.test_settings -v 1`
