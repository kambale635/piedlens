from django.apps import AppConfig


class PlatformConnectorsConfig(AppConfig):
    """Registers the Platform Connectors Django app.

    See docs/09-context-platform-connectors.md and docs/05-module-structure.md.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "contexts.platform_connectors"