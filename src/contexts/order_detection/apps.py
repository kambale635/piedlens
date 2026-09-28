from django.apps import AppConfig


class OrderDetectionConfig(AppConfig):
    """Registers the Order Detection Django app.

    See docs/11-context-order-detection.md and docs/05-module-structure.md.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "contexts.order_detection"