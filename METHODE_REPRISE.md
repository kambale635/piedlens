Fait : P1 validée, ciblés 18/18, migration synchronisée.
Prochaine action : commit A P1 par chemins explicites (sans `.github/copilot-instructions.md`), puis P2 Payments.
Test : `./venv/bin/python manage.py test tests.integration.platform_connectors.test_manual_conversation_import tests.unit.platform_connectors.test_channel_adapter_contract tests.unit.platform_connectors.test_manual_import_use_cases tests.architecture.test_architecture_boundaries --settings=config.test_settings -v 1`
