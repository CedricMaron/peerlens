"""The provider registry.

``ProviderManager`` is the only place that knows which providers exist. It is
deliberately independent of PeerLens research logic: it can create a provider
and report whether it can execute requests, and that is all. Readiness,
sections, issues and the manuscript gate live in ``services/``.

    PeerLens research engine
              |
        ProviderManager
      /     |      |      |      \\
 Claude   Codex  Anthropic OpenAI  Ollama
  Code                API     API
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .base import LLMProvider, ProviderConfig, ProviderStatus
from .claude_code import ClaudeCodeProvider
from .codex_cli import CodexProvider
from .errors import ErrorCode, LLMError
from .providers import AnthropicProvider, OllamaProvider, OpenAIProvider

ProviderKind = Literal["cli", "api", "local"]


@dataclass(frozen=True)
class ProviderSpec:
    """Everything the UI and the settings store need to know about a provider."""

    id: str
    label: str
    cls: type[LLMProvider]
    kind: ProviderKind
    blurb: str
    needs_api_key: bool = False
    requires_model: bool = False
    is_local: bool = False
    supports_login: bool = False
    is_subscription: bool = False
    default_model: str = ""
    default_base_url: str | None = None
    setup_hint: str = ""


SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        id="claude-code",
        label="Claude Code",
        cls=ClaudeCodeProvider,
        kind="cli",
        blurb=(
            "Uses your existing Claude account through the official Claude Code CLI. "
            "No API key. PeerLens never sees your Claude credentials."
        ),
        supports_login=True,
        is_subscription=True,
        setup_hint=(
            "Install Claude Code, then sign in with the official flow. Model selection "
            "is optional — leave it blank to use your Claude Code default."
        ),
    ),
    ProviderSpec(
        id="codex",
        label="OpenAI Codex",
        cls=CodexProvider,
        kind="cli",
        blurb=(
            "Uses your existing ChatGPT account through the official Codex CLI. "
            "No API key. PeerLens never sees your ChatGPT credentials."
        ),
        supports_login=True,
        is_subscription=True,
        setup_hint=(
            "Install the Codex CLI and connect it to ChatGPT. Model selection is "
            "optional — leave it blank to use your Codex default."
        ),
    ),
    ProviderSpec(
        id="anthropic",
        label="Anthropic API",
        cls=AnthropicProvider,
        kind="api",
        blurb="Claude models billed through an Anthropic API key.",
        needs_api_key=True,
        requires_model=True,
        default_model="claude-sonnet-4-5-20250929",
        default_base_url="https://api.anthropic.com",
        setup_hint="Create a key at console.anthropic.com. API billing is separate from a Claude subscription.",
    ),
    ProviderSpec(
        id="openai",
        label="OpenAI API",
        cls=OpenAIProvider,
        kind="api",
        blurb="OpenAI models billed through an OpenAI API key.",
        needs_api_key=True,
        requires_model=True,
        default_model="gpt-4.1",
        default_base_url="https://api.openai.com/v1",
        setup_hint="Create a key at platform.openai.com. API billing is separate from a ChatGPT subscription.",
    ),
    ProviderSpec(
        id="ollama",
        label="Ollama",
        cls=OllamaProvider,
        kind="local",
        blurb="Fully local models. No API key, and model inference never leaves your machine.",
        requires_model=True,
        is_local=True,
        default_model="llama3.1:8b",
        default_base_url="http://localhost:11434",
        setup_hint="Run `ollama serve` and pull a model, e.g. `ollama pull qwen3:8b`.",
    ),
)


class ProviderManager:
    def __init__(self, specs: tuple[ProviderSpec, ...] = SPECS):
        self._specs = {spec.id: spec for spec in specs}
        self._order = [spec.id for spec in specs]

    # -- registry ----------------------------------------------------------

    def ids(self) -> list[str]:
        return list(self._order)

    def specs(self) -> list[ProviderSpec]:
        return [self._specs[i] for i in self._order]

    def has(self, provider_id: str) -> bool:
        return provider_id in self._specs

    def spec(self, provider_id: str) -> ProviderSpec:
        try:
            return self._specs[provider_id]
        except KeyError:
            raise LLMError(
                f"Unknown AI provider: {provider_id}", ErrorCode.UNKNOWN_PROVIDER
            ) from None

    def register(self, spec: ProviderSpec) -> None:
        """Extension point: a new provider needs no changes elsewhere."""
        self._specs[spec.id] = spec
        if spec.id not in self._order:
            self._order.append(spec.id)

    # -- construction ------------------------------------------------------

    def get(self, config: ProviderConfig) -> LLMProvider:
        """Build the provider described by ``config``.

        The returned object executes AI requests. It has no access to research
        state and cannot change a section's status.
        """
        spec = self.spec(config.provider)
        return spec.cls(config)

    def default_config(self, provider_id: str) -> ProviderConfig:
        spec = self.spec(provider_id)
        return ProviderConfig(
            provider=spec.id, model=spec.default_model, base_url=spec.default_base_url
        )

    async def status(self, config: ProviderConfig) -> ProviderStatus:
        spec = self.spec(config.provider)
        status = await self.get(config).status()
        status.name = spec.label
        return status


provider_manager = ProviderManager()

#: Legacy alias: the class map keyed by provider id.
PROVIDERS: dict[str, type[LLMProvider]] = {
    spec.id: spec.cls for spec in provider_manager.specs()
}

DEFAULT_MODELS: dict[str, str] = {
    spec.id: spec.default_model for spec in provider_manager.specs()
}

DEFAULT_BASE_URLS: dict[str, str] = {
    spec.id: spec.default_base_url
    for spec in provider_manager.specs()
    if spec.default_base_url
}
