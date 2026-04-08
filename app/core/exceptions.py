class DomainError(Exception):
    status_code = 400
    error_code = "domain_error"

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class UnauthorizedError(DomainError):
    status_code = 401
    error_code = "unauthorized"


class ForbiddenError(DomainError):
    status_code = 403
    error_code = "forbidden"


class NotFoundError(DomainError):
    status_code = 404
    error_code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    error_code = "conflict"
