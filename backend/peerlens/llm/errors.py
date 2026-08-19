"""Normalized provider errors.

Every provider failure reaches PeerLens as an ``LLMError`` carrying one of the
codes below, so the UI can react to *what went wrong* rather than to a
provider-specific message. The message itself stays short and actionable;
verbose stderr goes to the server log, never to the browser.
"""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNKNOWN_PROVIDER = "UNKNOWN_PROVIDER"
    CLI_NOT_INSTALLED = "CLI_NOT_INSTALLED"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    AUTH_FAILED = "AUTH_FAILED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    INVALID_API_KEY = "INVALID_API_KEY"
    REQUEST_CANCELLED = "REQUEST_CANCELLED"
    REQUEST_TIMEOUT = "REQUEST_TIMEOUT"
    PROCESS_FAILED = "PROCESS_FAILED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"


class LLMError(RuntimeError):
    """Raised when a provider call fails or is not configured.

    ``code`` is a stable machine-readable classification; ``detail`` holds the
    developer-facing tail of provider output and is not shown in the UI.
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode | str = ErrorCode.UNKNOWN_PROVIDER_ERROR,
        detail: str = "",
    ):
        super().__init__(message)
        self.code = code.value if isinstance(code, ErrorCode) else str(code)
        self.detail = detail


def classify_http_status(status: int, body: str) -> ErrorCode:
    """Map an HTTP API failure onto a normalized code."""
    lowered = (body or "").lower()
    if status in (401, 403):
        return ErrorCode.INVALID_API_KEY
    if status == 429:
        return ErrorCode.RATE_LIMITED
    if status == 404 and "model" in lowered:
        return ErrorCode.MODEL_UNAVAILABLE
    if status == 400 and "model" in lowered and (
        "not found" in lowered or "does not exist" in lowered
    ):
        return ErrorCode.MODEL_UNAVAILABLE
    if status >= 500:
        return ErrorCode.PROVIDER_UNAVAILABLE
    return ErrorCode.UNKNOWN_PROVIDER_ERROR
