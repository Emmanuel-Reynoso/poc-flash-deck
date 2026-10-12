"""Domain errors. The HTTP layer maps them to status codes."""

from __future__ import annotations


class AppError(Exception):
    status: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class BadRequest(AppError):
    status = 400
    code = "bad_request"


class Unauthorized(AppError):
    status = 401
    code = "unauthorized"


class NotFound(AppError):
    status = 404
    code = "not_found"


class Conflict(AppError):
    status = 409
    code = "conflict"


class PayloadTooLarge(AppError):
    status = 413
    code = "payload_too_large"
