from django.conf import settings
from django.http import JsonResponse

from .route_policy import emit_audit


class RateLimitMiddleware:
	"""Enforce the configured IRateLimiter for authenticated requests."""

	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		return self.get_response(request)

	def process_view(self, request, view_func, view_args, view_kwargs):
		limiter = getattr(settings, "PIEDLENS_RATE_LIMITER", None)
		if getattr(view_func, "allow_anonymous", False) or limiter is None:
			return None
		allowed = limiter.allow(
			user_id=request.user.id,
			merchant_id=request.merchant_id,
			route=request.path,
		)
		if not allowed:
			emit_audit(request, "rate_limited", getattr(request, "verified_permission", None))
			return JsonResponse(
				{"errorCode": "RATE_LIMIT_EXCEEDED", "correlationId": getattr(request, "correlation_id", "")},
				status=429,
			)
		return None