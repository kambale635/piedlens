Fait : sous-étapes a/b/c/d commitées (`3ec75a3`, `8187cfc`, `107ffaa`, `dfaf7c6`); candidate/API, Backup snapshot/export et garde-fou CI validés.
Prochaine action : exécuter la concurrence sur une base PostgreSQL locale configurée; aucun identifiant de fournisseur live n’a été ajouté.
Test local : `REQUIRE_POSTGRES=1 ./venv/bin/python manage.py test tests.integration.billing.test_outbound_quota_concurrency --settings=config.ci_settings -v 2`; définir POSTGRES_DB/USER/PASSWORD/HOST/PORT dans l’environnement local.
