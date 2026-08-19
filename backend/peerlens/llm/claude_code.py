"""Claude Code provider — inference through the user's existing Claude account.

PeerLens shells out to the official ``claude`` CLI in its documented
machine-readable mode and converts the stream to normalized ``AIEvent``s.
Authentication is the CLI's business: ``claude auth login`` opens the official
flow in a browser, ``claude auth status --json`` reports the result. PeerLens
never sees an email, a password, a cookie or a token.

The CLI is invoked as a plain inference backend, not as a coding agent:

* ``--tools ""`` disables every built-in tool (no edits, no shell, no reads);
* ``--safe-mode`` ignores hooks, skills, plugins, MCP servers and CLAUDE.md;
* ``--strict-mcp-config`` refuses external MCP servers;
* the working directory is an empty scratch folder in the data directory.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable

from .base import AIEvent, AIRequest, ErrorCode, LLMUsage
from .cli_provider import CLIProvider, StreamState
from .process import Launcher

logger = logging.getLogger("peerlens.llm.claude_code")

INSTALL_HINT = (
    "Install Claude Code (https://claude.com/product/claude-code), then run "
    "`claude` once and sign in with your Claude account."
)


class ClaudeCodeProvider(CLIProvider):
    name = "claude-code"
    label = "Claude Code"
    binary_names = ("claude",)
    install_hint = INSTALL_HINT

    def build_args(self, request: AIRequest) -> list[str]:
        args = [
            "--print",
            "--output-format", "stream-json",
            "--verbose",  # required by the CLI for stream-json output
            "--safe-mode",
            "--tools", "",  # inference only: no tool is available to the model
            "--disable-slash-commands",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]
        if self.model:
            args += ["--model", self.model]
        return args

    def parse_line(self, line: str, state: StreamState) -> Iterable[AIEvent]:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, dict):
            return []

        kind = payload.get("type")
        if kind == "system":
            if payload.get("subtype") == "init":
                state.model = payload.get("model") or state.model
                return [AIEvent(type="status", message="Claude Code session started.")]
            return []

        if kind == "rate_limit_event":
            return [AIEvent(type="status", message="Claude Code reported a rate-limit event.")]

        if kind == "assistant":
            blocks = ((payload.get("message") or {}).get("content")) or []
            texts = [
                b.get("text", "")
                for b in blocks
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            joined = "".join(t for t in texts if t)
            if not joined:
                return []
            state.text_parts.append(joined)
            return [AIEvent(type="text_delta", text=joined)]

        if kind == "result":
            return list(self._result_events(payload, state))

        return []

    def _result_events(self, payload: dict, state: StreamState) -> Iterable[AIEvent]:
        usage_raw = payload.get("usage") or {}
        cached = usage_raw.get("cache_read_input_tokens")
        input_tokens = usage_raw.get("input_tokens")
        if input_tokens is not None:
            # Mirror the Anthropic API provider: cache reads are input tokens
            # that were served from cache, so they belong in the input total.
            input_tokens = input_tokens + (cached or 0) + (
                usage_raw.get("cache_creation_input_tokens") or 0
            )
        state.usage = LLMUsage(
            input_tokens=input_tokens,
            output_tokens=usage_raw.get("output_tokens"),
            cached_tokens=cached,
        )
        state.model = _model_from_usage(payload.get("modelUsage")) or state.model

        if payload.get("is_error") or payload.get("subtype") != "success":
            message, code = _classify_result_error(payload)
            yield AIEvent(type="error", message=message, code=code.value)
            return

        result_text = payload.get("result")
        if isinstance(result_text, str) and result_text.strip():
            state.final_text = result_text
        yield AIEvent(type="usage", usage=state.usage)

    async def check_auth(self, launcher: Launcher) -> tuple[bool | None, str]:
        """Ask the official CLI. PeerLens reads no credential file itself."""
        code, out, _ = await self.capture(launcher, ["auth", "status", "--json"])
        try:
            payload = json.loads(out)
        except (json.JSONDecodeError, TypeError):
            payload = None
        if not isinstance(payload, dict):
            if code == 0:
                return None, ""
            return False, "Not signed in. Run `claude auth login` or use Connect below."
        logged_in = bool(payload.get("loggedIn"))
        method = str(payload.get("authMethod") or "").strip()
        if logged_in:
            # Subscription tier is deliberately not reported: PeerLens only
            # needs to know whether requests can be executed.
            return True, f"Signed in via {method}." if method else "Signed in."
        return False, "Not signed in. Use Connect to run the official Claude login flow."

    # -- login -------------------------------------------------------------

    login_args: tuple[str, ...] = ("auth", "login")
    login_hint = (
        "The official Claude login page opens in your browser. If no browser is "
        "available, run `claude auth login` in a terminal on this machine."
    )


def _model_from_usage(model_usage: object) -> str:
    """Pick the model that produced most of the output, when reported."""
    if not isinstance(model_usage, dict) or not model_usage:
        return ""

    def output_tokens(entry: object) -> int:
        return int(entry.get("outputTokens") or 0) if isinstance(entry, dict) else 0

    return max(model_usage.items(), key=lambda kv: output_tokens(kv[1]))[0]


def _classify_result_error(payload: dict) -> tuple[str, ErrorCode]:
    errors = payload.get("errors")
    detail = " ".join(str(e) for e in errors) if isinstance(errors, list) else ""
    blob = f"{payload.get('subtype', '')} {detail} {payload.get('api_error_status', '')}".lower()
    if "credit" in blob or "429" in blob or ("rate" in blob and "limit" in blob):
        message = (
            "Claude Code reported a rate or usage limit. Wait and retry, or select "
            "another provider in Settings."
        )
        return message, ErrorCode.RATE_LIMITED
    if "auth" in blob or "401" in blob or "login" in blob:
        return (
            "Claude Code is not authenticated. Run the Claude login flow from Settings.",
            ErrorCode.NOT_AUTHENTICATED,
        )
    if "model" in blob and ("not" in blob or "unavailable" in blob):
        return ("The requested Claude model is unavailable.", ErrorCode.MODEL_UNAVAILABLE)
    logger.warning("Claude Code returned an error result: %s", str(payload)[:800])
    return (
        f"Claude Code could not complete the request ({payload.get('subtype') or 'error'}).",
        ErrorCode.PROVIDER_UNAVAILABLE,
    )
