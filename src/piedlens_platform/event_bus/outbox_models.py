"""Bounded-context Outbox model registry for the shared relay command."""

from importlib import import_module


OUTBOX_MODELS = {
    "access-control": "contexts.access_control.infrastructure.persistence.models",
    "backup": "contexts.backup.infrastructure.persistence.models",
    "crm": "contexts.crm.infrastructure.persistence.models",
    "identity": "contexts.identity.infrastructure.persistence.models",
    "order-detection": "contexts.order_detection.infrastructure.persistence.models",
    "platform-connectors": "contexts.platform_connectors.infrastructure.persistence.models",
    "rules-engine": "contexts.rules_engine.infrastructure.persistence.models",
}


def outbox_model_for(context_name: str):
    """Resolve the Outbox model without importing one context into another."""
    try:
        module_path = OUTBOX_MODELS[context_name]
    except KeyError as error:
        raise ValueError(f"Unknown Outbox context: {context_name}") from error
    return import_module(module_path).OutboxEventRecord