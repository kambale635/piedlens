from uuid import uuid4


class RequestIdMiddleware:
	"""Propagate a bounded correlation identifier across the HTTP request."""

	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		supplied_id = request.headers.get("X-Correlation-ID", "")
		request.correlation_id = supplied_id if 0 < len(supplied_id) <= 128 else str(uuid4())
		response = self.get_response(request)
		response["X-Correlation-ID"] = request.correlation_id
		return response