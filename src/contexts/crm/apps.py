from django.apps import AppConfig


class CRMConfig(AppConfig):
    """Registers the CRM Django app.

    See docs/12-context-crm.md and docs/05-module-structure.md.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "contexts.crm"