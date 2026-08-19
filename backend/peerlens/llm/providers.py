"""Concrete providers: OpenAI, Anthropic, Ollama.

Each returns whatever token accounting the API reports; nothing is estimated.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from ..config import LLM_TIMEOUT_SECONDS
from .base import (
    ErrorCode,
    LLMError,
    LLMProvider,
    LLMResult,
    LLMUsage,
    ProviderStatus,
    strip_reasoning,
)
from .errors import classify_http_status

JSON_INSTRUCTION = (
    "Respond with a single valid JSON object and nothing else. "
    "No markdown fences, no commentary before or after the JSON."
)


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(LLM_TIMEOUT_SECONDS, connect=15.0)


def _timeout_error(provider: str, exc: Exception) -> LLMError:
    """Timeouts are common on local models and need actionable guidance."""
    return LLMError(
        f"{provider} did not respond within {LLM_TIMEOUT_SECONDS:.0f}s. "
        "Scientific reviews send a large prompt, and local models on CPU can "
        "exceed this. Raise PEERLENS_LLM_TIMEOUT, use a smaller or faster model, "
        f"or reduce the amount of research material. ({type(exc).__name__})",
        ErrorCode.REQUEST_TIMEOUT,
    )


def _http_error(provider: str, response: httpx.Response) -> LLMError:
    detail = response.text[:600]
    try:
        payload = response.json()
        detail = str(payload.get("error") or payload.get("message") or payload)[:600]
    except Exception:  # noqa: BLE001 - non-JSON error body
        pass
    return LLMError(
        f"{provider} API error {response.status_code}: {detail}",
        classify_http_status(response.status_code, detail),
        detail=detail,
    )


class _APIKeyProvider(LLMProvider):
    """Shared status reporting for key-based cloud APIs.

    A key-based provider is "configured" when a key is stored. Whether that key
    is *valid* is only knowable by making a request, which Settings -> Test
    Connection does explicitly rather than on every status poll.
    """

    async def status(self) -> ProviderStatus:
        configured = bool(self.config.api_key)
        return ProviderStatus(
            id=self.name,
            name=self.name,
            state="ready" if configured else "not_configured",
            message="" if configured else "No API key stored.",
            configured=configured,
            model=self.model,
        )


class OpenAIProvider(_APIKeyProvider):
    name = "openai"

    async def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        max_tokens: int = 8000,
        temperature: float = 0.2,
    ) -> LLMResult:
        if not self.config.api_key:
            raise LLMError(
                "OpenAI API key is not configured (Settings -> AI Provider).",
                ErrorCode.NOT_CONFIGURED,
            )
        base = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        if system and json_mode:
            system = f"{system}\n\n{JSON_INSTRUCTION}"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=_timeout()) as client:
                data = await self._post_adaptive(client, f"{base}/chat/completions", payload)
        except httpx.TimeoutException as exc:
            raise _timeout_error("OpenAI", exc) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                f"Unexpected OpenAI response shape: {str(data)[:300]}",
                ErrorCode.INVALID_OUTPUT,
            ) from exc

        usage_raw = data.get("usage") or {}
        details = usage_raw.get("prompt_tokens_details") or {}
        usage = LLMUsage(
            input_tokens=usage_raw.get("prompt_tokens"),
            output_tokens=usage_raw.get("completion_tokens"),
            cached_tokens=details.get("cached_tokens"),
        )
        return LLMResult(
            text=strip_reasoning(text),
            provider=self.name,
            model=data.get("model") or self.model,
            usage=usage,
            latency_ms=latency_ms,
        )

    async def _post_adaptive(
        self, client: httpx.AsyncClient, url: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """POST, dropping parameters the target model rejects.

        Model families differ in whether they accept ``temperature`` or use
        ``max_tokens`` vs ``max_completion_tokens``. Rather than hardcoding a
        model list that ages badly, adapt to the API's own error message.
        """
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        body = dict(payload)
        for _ in range(4):
            response = await client.post(url, json=body, headers=headers)
            if response.status_code < 400:
                return response.json()
            if response.status_code != 400:
                raise _http_error("OpenAI", response)
            message = response.text
            adjusted = False
            if "max_completion_tokens" in message and "max_completion_tokens" in body:
                body["max_tokens"] = body.pop("max_completion_tokens")
                adjusted = True
            elif "'max_tokens'" in message and "max_tokens" in body:
                body["max_completion_tokens"] = body.pop("max_tokens")
                adjusted = True
            if "temperature" in message and "temperature" in body:
                body.pop("temperature")
                adjusted = True
            if "response_format" in message and "response_format" in body:
                body.pop("response_format")
                adjusted = True
            if not adjusted:
                raise _http_error("OpenAI", response)
        raise LLMError(
            "OpenAI rejected the request after parameter adaptation.",
            ErrorCode.UNKNOWN_PROVIDER_ERROR,
        )


class AnthropicProvider(_APIKeyProvider):
    name = "anthropic"

    async def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        max_tokens: int = 8000,
        temperature: float = 0.2,
    ) -> LLMResult:
        if not self.config.api_key:
            raise LLMError(
                "Anthropic API key is not configured (Settings -> AI Provider).",
                ErrorCode.NOT_CONFIGURED,
            )
        base = (self.config.base_url or "https://api.anthropic.com").rstrip("/")
        if json_mode:
            system = f"{system}\n\n{JSON_INSTRUCTION}"

        messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
        if json_mode:
            # Prefilling the assistant turn reliably forces a bare JSON object.
            messages.append({"role": "assistant", "content": "{"})

        payload = {
            "model": self.model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "x-api-key": self.config.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=_timeout()) as client:
                response = await client.post(f"{base}/v1/messages", json=payload, headers=headers)
                if response.status_code >= 400:
                    raise _http_error("Anthropic", response)
                data = response.json()
        except httpx.TimeoutException as exc:
            raise _timeout_error("Anthropic", exc) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        text = "".join(parts)
        if json_mode:
            text = "{" + text  # restore the prefilled opening brace

        usage_raw = data.get("usage") or {}
        cached = usage_raw.get("cache_read_input_tokens")
        input_tokens = usage_raw.get("input_tokens")
        if input_tokens is not None and cached:
            input_tokens = input_tokens + cached
        usage = LLMUsage(
            input_tokens=input_tokens,
            output_tokens=usage_raw.get("output_tokens"),
            cached_tokens=cached,
        )
        return LLMResult(
            text=strip_reasoning(text),
            provider=self.name,
            model=data.get("model") or self.model,
            usage=usage,
            latency_ms=latency_ms,
        )


class OllamaProvider(LLMProvider):
    name = "ollama"
    is_local = True

    async def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        max_tokens: int = 8000,
        temperature: float = 0.2,
    ) -> LLMResult:
        base = (self.config.base_url or "http://localhost:11434").rstrip("/")
        if json_mode:
            system = f"{system}\n\n{JSON_INSTRUCTION}"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=_timeout()) as client:
                response = await client.post(f"{base}/api/chat", json=payload)
                if response.status_code >= 400:
                    raise _http_error("Ollama", response)
                data = response.json()
        except httpx.TimeoutException as exc:
            raise _timeout_error("Ollama", exc) from exc
        except httpx.ConnectError as exc:
            raise LLMError(
                f"Cannot reach Ollama at {base}. Is `ollama serve` running? "
                "From Docker, use http://host.docker.internal:11434.",
                ErrorCode.PROVIDER_UNAVAILABLE,
            ) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        text = (data.get("message") or {}).get("content", "")
        usage = LLMUsage(
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
            cached_tokens=None,
        )
        return LLMResult(
            text=strip_reasoning(text),
            provider=self.name,
            model=data.get("model") or self.model,
            usage=usage,
            latency_ms=latency_ms,
            is_local=True,
        )

    async def status(self) -> ProviderStatus:
        """Local and cheap to check: is the daemon actually answering?"""
        base = (self.config.base_url or "http://localhost:11434").rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{base}/api/tags")
                response.raise_for_status()
                installed = [
                    m.get("name", "") for m in response.json().get("models", []) if m.get("name")
                ]
        except Exception:  # noqa: BLE001 - unreachable is a normal, reportable state
            return ProviderStatus(
                id=self.name,
                name=self.name,
                state="unavailable",
                message=f"No Ollama server answering at {base}. Run `ollama serve`.",
                configured=bool(self.model),
                model=self.model,
            )
        if not self.model:
            return ProviderStatus(
                id=self.name, name=self.name, state="not_configured",
                message="Running, but no model selected.", configured=False,
            )
        message = "Running." if self.model in installed else (
            f"Running, but '{self.model}' is not installed locally."
        )
        return ProviderStatus(
            id=self.name,
            name=self.name,
            state="ready" if self.model in installed else "not_configured",
            message=message,
            configured=True,
            model=self.model,
        )


async def list_ollama_models(base_url: str | None) -> list[str]:
    """Convenience for Settings: show what is actually installed locally."""
    base = (base_url or "http://localhost:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(f"{base}/api/tags")
            response.raise_for_status()
            return [m.get("name", "") for m in response.json().get("models", []) if m.get("name")]
    except Exception:  # noqa: BLE001 - Settings degrades to free-text model entry
        return []
