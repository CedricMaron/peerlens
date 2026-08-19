"""AI provider abstraction for PeerLens.

Providers execute AI requests. They never evaluate research, never decide that
a section is READY, and never unlock the manuscript — that logic lives in
``peerlens.services``.
"""

from .base import (
    AIEvent,
    AIRequest,
    LLMProvider,
    LLMResult,
    LLMUsage,
    ProviderConfig,
    ProviderStatus,
)
from .errors import ErrorCode, LLMError
from .manager import PROVIDERS, ProviderManager, ProviderSpec, provider_manager
from .providers import list_ollama_models

__all__ = [
    "PROVIDERS",
    "AIEvent",
    "AIRequest",
    "ErrorCode",
    "LLMError",
    "LLMProvider",
    "LLMResult",
    "LLMUsage",
    "ProviderConfig",
    "ProviderManager",
    "ProviderSpec",
    "ProviderStatus",
    "list_ollama_models",
    "provider_manager",
]
