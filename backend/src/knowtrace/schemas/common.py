"""Shared building blocks: error envelope, pagination parameters, base classes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

MAX_PAGE_SIZE = 100


class Response(BaseModel):
    """Base for every response schema: built from service result objects, never from ORM rows."""

    model_config = ConfigDict(from_attributes=True)


class Request(BaseModel):
    """Base for every request schema: unknown fields are an error."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ErrorDetail(BaseModel):
    loc: list[str | int] = Field(
        default_factory=list, description="Where the problem is, e.g. ['body', 'answer']"
    )
    message: str
    type: str | None = None


class ErrorBody(BaseModel):
    code: str = Field(description="Stable machine-readable code, e.g. validation_error, not_found")
    message: str
    details: list[ErrorDetail] | dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    """The one error shape used by every endpoint."""

    error: ErrorBody


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorEnvelope, "description": "Bad request"},
    404: {"model": ErrorEnvelope, "description": "Not found"},
    409: {"model": ErrorEnvelope, "description": "Not allowed in the current state"},
    422: {"model": ErrorEnvelope, "description": "Validation error"},
    429: {"model": ErrorEnvelope, "description": "Rate limited"},
    500: {"model": ErrorEnvelope, "description": "Unexpected error"},
    503: {"model": ErrorEnvelope, "description": "Not ready"},
}

Limit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE, description="Page size (max 100)")]
Offset = Annotated[int, Query(ge=0, description="Rows to skip")]


class PageMeta(Response):
    total: int
    limit: int
    offset: int
