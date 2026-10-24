Fait : sous-étape a commitée (`3ec75a3`); E2E paiement/livraison signé passe (`tests.integration.test_e2e_message_to_dormant_order`).
Prochaine action : terminer et committer l’E2E faible confiance/API, puis confirmer Backup snapshot/export et activer le garde-fou PostgreSQL CI.
Test : `./venv/bin/python manage.py test tests.integration.test_e2e_detection_candidate_review --settings=config.test_settings -v 1`
