from django.apps import AppConfig


class AccessControlConfig(AppConfig):
    """Registers the Access Control Django app.

    See docs/20-context-access-control.md and docs/05-module-structure.md.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "contexts.access_control"