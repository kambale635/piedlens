from django.apps import AppConfig


class BackupConfig(AppConfig):
    """Registers the Backup Django app.

    See docs/10-context-backup.md and docs/05-module-structure.md.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "contexts.backup"