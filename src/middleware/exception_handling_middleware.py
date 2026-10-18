import logging

from django.http import JsonResponse
from django.core.exceptions import RequestDataTooBig
from django.utils.deprecation import MiddlewareMixin

from shared_kernel.application_exceptions import (
	ApplicationException,
	ResourceNotFoundException,
	ValidationException,
)
from shared_kernel.domain_exceptions import DomainException


logger = logging.getLogger(__name__)


class ExceptionHandlingMiddleware(MiddlewareMixin):
	"""Translate application failures to a stable API envelope without leaking internals."""

	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		try:
			return self.get_response(request)
		except Exception as error:
			return self._exception_response(request, error)

	def process_exception(self, request, error):
		"""Translate view exceptions through Django's supported exception hook."""
		return self._exception_response(request, error)

	@staticmethod
	def _exception_response(request, error):
		correlation_id = getattr(request, "correlation_id", "")
		if isinstance(error, RequestDataTooBig):
			status, code = 413, "REQUEST_TOO_LARGE"
		elif isinstance(error, ResourceNotFoundException):
			status, code = 404, "NOT_FOUND"
		elif isinstance(error, ValidationException):
			status = getattr(error, "status_code", 400)
			code = getattr(error, "error_code", "VALIDATION_ERROR")
		elif isinstance(error, (ApplicationException, DomainException)) and hasattr(error, "error_code"):
			status = getattr(error, "status_code", 422)
			code = error.error_code
		elif isinstance(error, DomainException):
			status, code = 422, "BUSINESS_RULE_VIOLATION"
		else:
			logger.error(
				"Unhandled request failure correlation_id=%s exception_type=%s",
				correlation_id,
				type(error).__name__,
			)
			status, code = 500, "INTERNAL_ERROR"
		return JsonResponse({"errorCode": code, "correlationId": correlation_id}, status=status)