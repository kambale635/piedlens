from django.apps import AppConfig


class IdentityConfig(AppConfig):
    """Registers the Identity Django app.

    See docs/02-domain-model.md, docs/15-use-cases-catalog.md, and
    docs/05-module-structure.md.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "contexts.identity"