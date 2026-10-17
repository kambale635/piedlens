from shared_kernel.application_exceptions import ApplicationException


class ReminderAlreadyScheduledException(ApplicationException):
    """Signals the INV-OD-06 conflict for an already scheduled order/type pair."""