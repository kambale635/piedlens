from django.conf import settings
from django.http import JsonResponse
from django.utils.module_loading import import_string

from .route_policy import emit_audit


class AuthenticationMiddleware:
	"""Require an authenticated principal unless a route is explicitly public."""

	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		return self.get_response(request)

	def process_view(self, request, view_func, view_args, view_kwargs):
		is_public = getattr(view_func, "public_route", False) or getattr(view_func, "allow_anonymous", False)
		if is_public and not getattr(view_func, "authentication_required", False):
			return None
			return None
		authenticator = getattr(settings, "PIEDLENS_AUTHENTICATOR", None)
		if isinstance(authenticator, str):
			authenticator = import_string(authenticator)
		principal = authenticator(request) if authenticator else getattr(request, "user", None)
		if principal is not None and getattr(principal, "is_authenticated", False):
			request.user = principal
			return None
		emit_audit(request, "denied", "authentication")
		return JsonResponse(
			{"errorCode": "UNAUTHENTICATED", "correlationId": getattr(request, "correlation_id", "")},
			status=401,
		)