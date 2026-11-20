"""Integration errors. Distinct from `DomainError`: these describe an unreliable outside world."""

from __future__ import annotations


class IntegrationError(Exception):
    """Base class for failures talking to a third party."""


class LLMError(IntegrationError):
    """A model call failed. `retryable` says whether repeating the same request may succeed."""

    retryable: bool = False


class LLMTimeoutError(LLMError):
    retryable = True


class LLMRateLimitError(LLMError):
    retryable = True


class LLMProviderError(LLMError):
    """Provider-side failure. 5xx and connection errors are retryable; other 4xx (auth, bad
    request) are not, because sending the same request again cannot fix them."""

    def __init__(self, message: str, *, status: int | None = None, retryable: bool | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable if retryable is not None else (status is None or status >= 500)


class LLMUnavailableError(LLMError):
    """No client is configured or the optional SDK is not installed."""
