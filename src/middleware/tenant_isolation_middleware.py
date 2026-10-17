from django.conf import settings
from django.http import JsonResponse

from .route_policy import emit_audit


class TenantIsolationMiddleware:
	"""Resolve the trusted merchant scope from the authenticated principal only."""

	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		return self.get_response(request)

	def process_view(self, request, view_func, view_args, view_kwargs):
		if getattr(view_func, "public_route", False) and getattr(view_func, "authentication_required", False):
			request.merchant_id = None
			return None
		if getattr(view_func, "allow_anonymous", False):
			return None
		resolver = getattr(settings, "PIEDLENS_TENANT_RESOLVER", None)
		merchant_id = resolver(request.user) if resolver else getattr(request.user, "merchant_id", None)
		if merchant_id is None:
			emit_audit(request, "denied", "tenant")
			return JsonResponse(
				{"errorCode": "TENANT_REQUIRED", "correlationId": getattr(request, "correlation_id", "")},
				status=403,
			)
		request.merchant_id = merchant_id
		return None