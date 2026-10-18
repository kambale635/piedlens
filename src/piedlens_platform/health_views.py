from datetime import datetime, timezone
import hmac
import logging

import redis
from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from django.utils.module_loading import import_string

from middleware.route_policy import public_route
from piedlens_platform.event_bus.outbox_models import OUTBOX_MODELS, outbox_model_for


logger = logging.getLogger("piedlens.health")


@public_route
def live(request):
    """Report process liveness without checking backing services."""
    return JsonResponse({"status": "live"})


@public_route
def ready(request):
    """Report whether PostgreSQL and Redis accept a cheap readiness probe."""
    failures = []
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        failures.append("database")
    try:
        _redis_client().ping()
    except Exception:
        failures.append("redis")
    status = 503 if failures else 200
    return JsonResponse(
        {"status": "not_ready" if failures else "ready", "failedChecks": failures},
        status=status,
    )


@public_route
def metrics(request):
    """Return Outbox lag and DLQ sizes and invoke the configured alert hook on thresholds."""
    authorization = request.headers.get("Authorization", "")
    scheme, _, supplied_token = authorization.partition(" ")
    if (
        not settings.HEALTH_METRICS_TOKEN
        or scheme.lower() != "bearer"
        or not hmac.compare_digest(supplied_token, settings.HEALTH_METRICS_TOKEN)
    ):
        return JsonResponse({"errorCode": "UNAUTHORIZED"}, status=401)
    now = datetime.now(timezone.utc)
    try:
        outbox_lag = _outbox_lag_seconds(now)
        dlq_sizes = _dead_letter_sizes()
    except Exception:
        return JsonResponse({"status": "metrics_unavailable"}, status=503)

    metrics_payload = {"outboxLagSeconds": outbox_lag, "deadLetterQueueSizes": dlq_sizes}
    alerts = []
    for context_name, lag_seconds in outbox_lag.items():
        if lag_seconds >= settings.HEALTH_OUTBOX_LAG_ALERT_SECONDS:
            alerts.append({"type": "outbox_lag", "context": context_name, "value": lag_seconds})
    for stream_name, size in dlq_sizes.items():
        if size >= settings.HEALTH_DLQ_SIZE_ALERT_THRESHOLD:
            alerts.append({"type": "dead_letter_queue", "stream": stream_name, "value": size})
    if alerts:
        _emit_alert({"alerts": alerts, "metrics": metrics_payload})
    return JsonResponse({"status": "ok", **metrics_payload})


def _outbox_lag_seconds(now):
    from django.db.models import Min

    lag_by_context = {}
    for context_name in OUTBOX_MODELS:
        model = outbox_model_for(context_name)
        oldest = model.objects.filter(published_at__isnull=True).aggregate(
            occurred_at=Min("occurred_at")
        )["occurred_at"]
        lag_by_context[context_name] = (
            max(0, int((now - oldest).total_seconds())) if oldest is not None else 0
        )
    return lag_by_context


def _dead_letter_sizes():
    client = _redis_client()
    return {
        f"{context_name}.dlq": client.xlen(f"{context_name}.dlq")
        for context_name in OUTBOX_MODELS
    }


def _redis_client():
    return redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        **({"ssl_ca_certs": settings.REDIS_TLS_CA_CERTS} if settings.REDIS_TLS_CA_CERTS else {}),
    )


def _emit_alert(event):
    hook = settings.PIEDLENS_ALERT_HOOK
    if not hook:
        return
    try:
        if isinstance(hook, str):
            hook = import_string(hook)
        hook(event)
    except Exception as error:
        logger.error("Health alert hook failed exception_type=%s", type(error).__name__)
