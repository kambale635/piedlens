import logging

from .route_policy import emit_audit


logger = logging.getLogger("piedlens.audit")


class AuditLoggingMiddleware:
	"""Record request outcome and access metadata, never request or message bodies."""

	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		response = self.get_response(request)
		emit_audit(
			request,
			"allowed" if response.status_code < 400 else "failed",
			getattr(request, "verified_permission", None),
		)
		logger.info(
			"HTTP audit",
			extra={
				"correlation_id": getattr(request, "correlation_id", None),
				"user_id": str(getattr(getattr(request, "user", None), "id", "") or ""),
				"merchant_id": str(getattr(request, "merchant_id", "") or ""),
				"route": request.path,
				"status_code": response.status_code,
			},
		)
		return response