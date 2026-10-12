"""Maps errors to the JSON error shape the frontend expects."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .errors import AppError

log = logging.getLogger(__name__)

NO_STORE = {"Cache-Control": "no-store"}


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status, headers=NO_STORE)


def _validation_message(exc: RequestValidationError) -> str:
    first = exc.errors()[0]
    if first["type"] == "json_invalid":
        return "The request body must be valid JSON."
    field = ".".join(str(part) for part in first["loc"] if part != "body")
    return f"{field}: {first['msg']}" if field else first["msg"]


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(400, "bad_request", _validation_message(exc))

    @app.exception_handler(HTTPException)
    def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    def unexpected_error(request: Request, _: Exception) -> JSONResponse:
        # Last-resort guard: details go to logs only.
        log.exception("Unhandled error in %s %s", request.method, request.url.path)
        return error_response(500, "internal_error", "Unexpected error.")
