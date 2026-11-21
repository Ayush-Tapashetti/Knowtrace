"""The only place that maps exceptions to HTTP status codes and the error envelope."""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from knowtrace.domain.errors import (
    DomainError,
    IllegalTransitionError,
    InvalidAnswerError,
    NoContentError,
    UnknownConceptError,
)
from knowtrace.services.errors import (
    BadRequestError,
    ConflictError,
    CurriculumNotLoadedError,
    NotFoundError,
    ServiceError,
)

log = logging.getLogger("knowtrace.api")


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name.removesuffix("Error")).lower()


def envelope(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"code": code, "message": message, "details": details}}
    )


def domain_status(exc: DomainError) -> int:
    if isinstance(exc, IllegalTransitionError):
        return 409
    if isinstance(exc, InvalidAnswerError):
        return 422
    if isinstance(exc, UnknownConceptError):
        return 404
    if isinstance(exc, NoContentError):
        return 500
    return 400


def service_status(exc: ServiceError) -> int:
    if isinstance(exc, NotFoundError):
        return 404
    if isinstance(exc, ConflictError):
        return 409
    if isinstance(exc, CurriculumNotLoadedError):
        return 503
    if isinstance(exc, BadRequestError):
        return 400
    return 400


async def _domain(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    status = domain_status(exc)
    if status == 500:  # content problem on our side: log it, show a safe message
        log.error("domain content error: %s", exc)
        return envelope(500, _snake(type(exc).__name__), "The lesson content for this topic is incomplete.")
    return envelope(status, _snake(type(exc).__name__), str(exc))


async def _service(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ServiceError)
    status = service_status(exc)
    code = {404: "not_found", 409: "conflict", 503: "not_ready"}.get(status, "bad_request")
    return envelope(status, code, exc.message, exc.details or None)


async def _validation(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [{"loc": list(e["loc"]), "message": e["msg"], "type": e["type"]} for e in exc.errors()]
    return envelope(422, "validation_error", "The request is not valid.", details)


async def _http(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    return envelope(exc.status_code, code, str(exc.detail))


async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return envelope(500, "internal_error", "Something went wrong on our side.")


def install(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain)
    app.add_exception_handler(ServiceError, _service)
    app.add_exception_handler(RequestValidationError, _validation)
    app.add_exception_handler(StarletteHTTPException, _http)
    app.add_exception_handler(Exception, _unexpected)
