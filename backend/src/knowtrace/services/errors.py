"""Service-level errors. Routers map these to HTTP codes in one place (routers/errors.py)."""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for expected, non-domain failures."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(ServiceError):
    def __init__(self, kind: str, ident: str) -> None:
        super().__init__(f"{kind} not found: {ident!r}", details={"kind": kind, "id": ident})


class ConflictError(ServiceError):
    """The request is valid but not allowed in the current state."""


class BadRequestError(ServiceError):
    """The request is well-formed JSON but semantically wrong for this resource."""


class CurriculumNotLoadedError(ServiceError):
    def __init__(self) -> None:
        super().__init__("curriculum is not loaded; run the seed command first")
