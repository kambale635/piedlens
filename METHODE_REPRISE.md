Fait : sous-étapes a/b commitées (`3ec75a3`, `8187cfc`); E2E faible confiance/API passe; Backup snapshot chiffré + export signé confirmé (3 tests).
Prochaine action : commit c, puis rendre le test de concurrence quota obligatoire en CI via `REQUIRE_POSTGRES=1` et vérifier qu’il n’est pas ignoré.
Test : `./venv/bin/python manage.py test tests.integration.test_e2e_detection_candidate_review tests.integration.backup.test_backup_exports.BackupExportIntegrationTests.test_signed_url_retrieves_only_the_signed_object --settings=config.test_settings -v 1`
