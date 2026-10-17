import json
from uuid import UUID

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from middleware.route_policy import requires_permission
from piedlens_platform.di.container import ApplicationContainer


@csrf_exempt
@requires_permission("rule_config.edit", global_scope_param="scope")
@require_http_methods(["PUT"])
def update_rule_set(request, scope):
    """Update RuleConfig after permission middleware verifies both tenant/global scopes."""
    payload = json.loads(request.body or b"{}")
    result = ApplicationContainer.update_rule_set().execute(
        scope=scope,
        rules=payload.get("rules", []),
        merchant_id=UUID(str(request.merchant_id)),
    )
    return JsonResponse(
        {"ruleSetId": result["rule_set_id"], "version": result["version"]},
        encoder=DjangoJSONEncoder,
    )