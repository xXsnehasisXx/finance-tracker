"""Domain exceptions mapped to HTTP responses in main.py."""


class AppError(Exception):
    status_code = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NotFoundError(AppError):
    status_code = 404


class ForbiddenError(AppError):
    status_code = 403


class ConflictError(AppError):
    status_code = 409


class InsufficientBalanceError(AppError):
    status_code = 400


class DomainValidationError(AppError):
    status_code = 422
