"""Provider-agnostic LLM interface.

A provider answers exactly one question: *execute this AI request*. It never
decides whether a research section is READY -- that judgment belongs to
``services/readiness.py`` and ``services/analysis.py``.
"""

from __future__ import annotations

import abc
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal

from .errors import ErrorCode, LLMError

__all__ = [
    "AIEvent",
    "AIRequest",
    "ErrorCode",
    "LLMError",
    "LLMProvider",
    "LLMResult",
    "LLMUsage",
    "ProviderConfig",
    "ProviderStatus",
    "strip_reasoning",
]

_REASONING_BLOCK = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """Remove reasoning blocks that local reasoning models emit inline.

    PeerLens shows structured conclusions, never a model's internal monologue.
    """
    if not text:
        return text
    cleaned = _REASONING_BLOCK.sub("", text)
    # An unterminated opening tag means the response was cut off mid-reasoning.
    if "<think>" in cleaned.lower() and "</think>" not in cleaned.lower():
        cleaned = re.split(r"<think>", cleaned, flags=re.IGNORECASE)[0]
    return cleaned.strip()


@dataclass
class LLMUsage:
    """Token accounting. ``None`` means the provider did not report the value.

    PeerLens never estimates or fabricates token counts.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    latency_ms: int = 0
    is_local: bool = False


@dataclass
class ProviderConfig:
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None


TaskType = Literal[
    "analyze_research",
    "check_section",
    "challenge_research",
    "compile_manuscript",
    "paper_analysis",
    "general",
]


@dataclass
class AIRequest:
    """A provider-independent inference request.

    Ordinary research requests never need filesystem or tool access: they carry
    all of their material in ``prompt``.
    """

    prompt: str
    system_prompt: str = ""
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    task_type: TaskType = "general"
    json_mode: bool = False
    max_tokens: int = 8000
    temperature: float = 0.2
    paper_id: int | None = None


@dataclass
class AIEvent:
    """A normalized streaming event, identical in shape for every provider."""

    type: Literal["start", "text_delta", "status", "usage", "complete", "error"]
    request_id: str = ""
    text: str = ""
    message: str = ""
    code: str = ""
    model: str = ""
    usage: LLMUsage | None = None


@dataclass
class ProviderStatus:
    """What Settings needs to know: can this provider execute a request?

    ``state`` is one of ``ready``, ``not_installed``, ``not_authenticated``,
    ``not_configured``, ``unavailable``, ``unknown`` or ``error``. Subscription
    tiers are deliberately not inferred.
    """

    id: str
    name: str
    state: str
    message: str = ""
    installed: bool | None = None
    authenticated: bool | None = None
    configured: bool = False
    version: str = ""
    model: str = ""

    @property
    def available(self) -> bool:
        return self.state == "ready"


class LLMProvider(abc.ABC):
    name: str = "base"
    is_local: bool = False
    #: Providers billed through a Claude/ChatGPT subscription rather than
    #: per-token API pricing. Their cost is never estimated.
    is_subscription: bool = False

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.model = config.model

    # -- inference ---------------------------------------------------------

    @abc.abstractmethod
    async def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        max_tokens: int = 8000,
        temperature: float = 0.2,
    ) -> LLMResult:
        """Single-turn completion."""

    async def complete_for(self, request: AIRequest) -> LLMResult:
        """Execute an :class:`AIRequest` and return the whole result.

        This is the entry point PeerLens uses: every scientific call needs the
        complete document before it can be validated, so streaming is an
        implementation detail of the providers that support it.
        """
        return await self.complete(
            system=request.system_prompt,
            user=request.prompt,
            json_mode=request.json_mode,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )

    async def run(self, request: AIRequest) -> AsyncIterator[AIEvent]:
        """Execute ``request``, emitting normalized events.

        The default implementation adapts a non-streaming ``complete()``: HTTP
        providers gain the shared event shape without streaming plumbing that
        PeerLens does not need (every response is parsed as a whole JSON
        document). CLI providers override this with real incremental output.
        """
        yield AIEvent(type="start", request_id=request.request_id)
        try:
            result = await self.complete(
                system=request.system_prompt,
                user=request.prompt,
                json_mode=request.json_mode,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
        except LLMError as exc:
            yield AIEvent(
                type="error", request_id=request.request_id, message=str(exc), code=exc.code
            )
            return
        yield AIEvent(type="usage", request_id=request.request_id, usage=result.usage)
        yield AIEvent(
            type="complete",
            request_id=request.request_id,
            text=result.text,
            model=result.model,
            usage=result.usage,
        )

    async def cancel(self, request_id: str) -> bool:
        """Stop an in-flight request. Returns True if something was stopped."""
        return False

    # -- status ------------------------------------------------------------

    async def status(self) -> ProviderStatus:
        """Can this provider currently execute requests?"""
        configured = self.is_local or bool(self.config.api_key)
        return ProviderStatus(
            id=self.name,
            name=self.name,
            state="ready" if (configured and self.model) else "not_configured",
            configured=configured,
            model=self.model,
        )

    async def test_connection(self) -> tuple[bool, str]:
        """Cheap round-trip used by Settings -> Test Connection."""
        try:
            result = await self.complete(
                system="You are a connectivity probe.",
                user="Reply with the single word: ok",
                # Generous budget: local reasoning models spend tokens thinking
                # before they answer, and an empty reply looks like a failure.
                max_tokens=512,
                temperature=0.0,
            )
        except LLMError as exc:
            return False, str(exc)
        except Exception as exc:  # noqa: BLE001 - surfaced verbatim to the user
            return False, f"{type(exc).__name__}: {exc}"
        text = (result.text or "").strip()
        label = result.model or self.model or "default model"
        return True, f"Connected to {self.name} ({label}). Reply: {text[:80] or '(empty)'}"
