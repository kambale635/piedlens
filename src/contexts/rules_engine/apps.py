from django.apps import AppConfig


class RulesEngineConfig(AppConfig):
    """Registers the shared Rules Engine Django app.

    See docs/08-context-rules-engine.md and docs/05-module-structure.md.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "contexts.rules_engine"