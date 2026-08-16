"""Provider-agnostic LLM interface."""

from __future__ import annotations

import abc
import re
from dataclasses import dataclass, field

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


class LLMError(RuntimeError):
    """Raised when a provider call fails or is not configured."""


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


class LLMProvider(abc.ABC):
    name: str = "base"
    is_local: bool = False

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.model = config.model

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
        return True, f"Connected to {self.name} ({self.model}). Reply: {text[:80] or '(empty)'}"
