from django.conf import settings
from django.http import JsonResponse
from django.utils.module_loading import import_string

from .route_policy import emit_audit


class PermissionMiddleware:
	"""Delegate every declared route permission to the Access Control port."""

	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		return self.get_response(request)

	def process_view(self, request, view_func, view_args, view_kwargs):
		if getattr(view_func, "public_route", False) or getattr(view_func, "allow_anonymous", False):
			return None
		permission = getattr(view_func, "required_permission", None)
		checker = getattr(settings, "PIEDLENS_PERMISSION_CHECKER", None)
		if isinstance(checker, str):
			checker = import_string(checker)()
		allowed = bool(permission and checker and checker.can(
			user_id=request.user.id,
			permission=permission,
			scope=request.merchant_id,
		))
		if not allowed:
			emit_audit(request, "denied", permission)
			return JsonResponse(
				{"errorCode": "FORBIDDEN", "correlationId": getattr(request, "correlation_id", "")},
				status=403,
			)
		request.verified_permission = permission
		return None