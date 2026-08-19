"""OpenAI Codex provider — inference through the user's existing ChatGPT account.

PeerLens shells out to the official ``codex`` CLI in its machine-readable
``codex exec --json`` mode. Authentication is delegated to ``codex login``,
which runs the official ChatGPT sign-in flow in a browser; PeerLens never
requests or stores a ChatGPT password, cookie or OAuth token.

Codex is used as an inference backend, not as a coding agent: the sandbox is
``read-only`` and the working directory is an empty scratch folder, so a
research request cannot modify anything.

The JSONL event vocabulary has changed between Codex releases, so the parser
below accepts both the ``{"msg": {...}}`` and the ``{"type": "item.completed"}``
shapes and ignores anything it does not recognise.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable

from .base import AIEvent, AIRequest, ErrorCode, LLMUsage
from .cli_provider import CLIProvider, StreamState
from .process import Launcher

logger = logging.getLogger("peerlens.llm.codex")

INSTALL_HINT = (
    "Install the Codex CLI (`npm install -g @openai/codex`), then connect it to "
    "your ChatGPT account with `codex login`."
)


class CodexProvider(CLIProvider):
    name = "codex"
    label = "OpenAI Codex"
    binary_names = ("codex",)
    install_hint = INSTALL_HINT

    def build_args(self, request: AIRequest) -> list[str]:
        args = [
            "exec",
            "--json",
            "--sandbox", "read-only",  # inference only: nothing may be written
            "--skip-git-repo-check",
        ]
        if self.model:
            args += ["--model", self.model]
        args.append("-")  # read the prompt from stdin
        return args

    def parse_line(self, line: str, state: StreamState) -> Iterable[AIEvent]:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, dict):
            return []
        if isinstance(payload.get("msg"), dict):
            return list(self._legacy_events(payload["msg"], state))
        return list(self._typed_events(payload, state))

    # -- {"id": .., "msg": {"type": ..}} -----------------------------------

    def _legacy_events(self, msg: dict, state: StreamState) -> Iterable[AIEvent]:
        kind = msg.get("type")
        if kind == "agent_message_delta":
            delta = msg.get("delta") or ""
            if delta:
                state.text_parts.append(delta)
                yield AIEvent(type="text_delta", text=delta)
        elif kind == "agent_message":
            text = msg.get("message") or msg.get("text") or ""
            if text:
                state.final_text = text
                yield AIEvent(type="text_delta", text=text)
        elif kind == "task_complete":
            text = msg.get("last_agent_message")
            if isinstance(text, str) and text.strip():
                state.final_text = text
        elif kind == "token_count":
            usage = _usage_from(
                (msg.get("info") or {}).get("total_token_usage") or msg.get("info") or msg
            )
            if usage is not None:
                state.usage = usage
                yield AIEvent(type="usage", usage=usage)
        elif kind in {"error", "stream_error"}:
            message, code = _classify(str(msg.get("message") or ""))
            yield AIEvent(type="error", message=message, code=code.value)
        elif kind == "session_configured":
            state.model = msg.get("model") or state.model
            yield AIEvent(type="status", message="Codex session started.")

    # -- {"type": "item.completed", ..} ------------------------------------

    def _typed_events(self, payload: dict, state: StreamState) -> Iterable[AIEvent]:
        kind = payload.get("type") or ""
        if kind in {"item.completed", "item.updated"}:
            item = payload.get("item") or {}
            if item.get("type") in {"agent_message", "assistant_message", "message"}:
                text = item.get("text") or item.get("message") or ""
                if text:
                    state.final_text = text
                    yield AIEvent(type="text_delta", text=text)
        elif kind in {"item.delta", "response.output_text.delta"}:
            delta = payload.get("delta") or payload.get("text") or ""
            if delta:
                state.text_parts.append(delta)
                yield AIEvent(type="text_delta", text=delta)
        elif kind == "turn.completed":
            usage = _usage_from(payload.get("usage"))
            if usage is not None:
                state.usage = usage
                yield AIEvent(type="usage", usage=usage)
        elif kind in {"turn.failed", "error"}:
            error = payload.get("error")
            raw = error.get("message") if isinstance(error, dict) else payload.get("message")
            message, code = _classify(str(raw or ""))
            yield AIEvent(type="error", message=message, code=code.value)
        elif kind == "thread.started":
            state.model = payload.get("model") or state.model
            yield AIEvent(type="status", message="Codex session started.")

    async def check_auth(self, launcher: Launcher) -> tuple[bool | None, str]:
        code, out, err = await self.capture(launcher, ["login", "status"])
        blob = f"{out} {err}".strip()
        lowered = blob.lower()
        if "not logged in" in lowered or "run `codex login`" in lowered:
            return False, "Not connected. Use Connect ChatGPT to run the official login."
        if code == 0 and ("logged in" in lowered or "authenticated" in lowered):
            return True, blob.splitlines()[0][:120] if blob else "Connected."
        if code != 0:
            return False, "Not connected. Use Connect ChatGPT to run the official login."
        return None, ""

    # -- login -------------------------------------------------------------

    login_args: tuple[str, ...] = ("login",)
    login_hint = (
        "The official ChatGPT sign-in page opens in your browser. If no browser is "
        "available, run `codex login` in a terminal on this machine."
    )


def _usage_from(raw: object) -> LLMUsage | None:
    """Read whatever token counts Codex reports; never invent one."""
    if not isinstance(raw, dict):
        return None
    input_tokens = raw.get("input_tokens")
    output_tokens = raw.get("output_tokens")
    cached = raw.get("cached_input_tokens")
    if input_tokens is None and output_tokens is None:
        return None
    return LLMUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached,
    )


def _classify(message: str) -> tuple[str, ErrorCode]:
    lowered = message.lower()
    if "rate limit" in lowered or "429" in lowered or "quota" in lowered:
        message = (
            "Codex reported a rate or usage limit. Wait and retry, or select another "
            "provider in Settings."
        )
        return message, ErrorCode.RATE_LIMITED
    if "not logged in" in lowered or "unauthorized" in lowered or "401" in lowered:
        return (
            "Codex is not connected to a ChatGPT account. Use Connect ChatGPT in Settings.",
            ErrorCode.NOT_AUTHENTICATED,
        )
    if "model" in lowered and ("not found" in lowered or "unavailable" in lowered):
        return ("The requested Codex model is unavailable.", ErrorCode.MODEL_UNAVAILABLE)
    logger.warning("Codex reported an error: %s", message[:800])
    short = message.strip().splitlines()[0][:200] if message.strip() else "unknown error"
    return (f"Codex could not complete the request: {short}", ErrorCode.PROVIDER_UNAVAILABLE)
