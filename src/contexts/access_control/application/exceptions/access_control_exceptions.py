from shared_kernel.application_exceptions import ApplicationException


class AccessControlApplicationException(ApplicationException):
    status_code = 400
    error_code = "ACCESS_CONTROL_ERROR"


class UnknownPermission(AccessControlApplicationException):
    error_code = "UNKNOWN_PERMISSION"


class RoleNameAlreadyExists(AccessControlApplicationException):
    status_code = 409
    error_code = "ROLE_NAME_ALREADY_EXISTS"


class RoleNotFound(AccessControlApplicationException):
    status_code = 404
    error_code = "ROLE_NOT_FOUND"


class RoleAssignmentNotFound(AccessControlApplicationException):
    status_code = 404
    error_code = "ROLE_ASSIGNMENT_NOT_FOUND"