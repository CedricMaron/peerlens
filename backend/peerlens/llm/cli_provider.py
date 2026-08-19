"""Shared behaviour for providers backed by an official local CLI.

Claude Code and Codex are used here as **inference backends**, not as coding
agents: tools are disabled, the working directory is an empty scratch folder
inside the PeerLens data directory, and the research prompt is delivered on
stdin. Authentication stays entirely owned by the official CLI -- PeerLens never
asks for a password, a cookie or a session token, and never reads a credential
file.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field

from .. import config
from . import process
from .base import (
    AIEvent,
    AIRequest,
    ErrorCode,
    LLMError,
    LLMProvider,
    LLMResult,
    LLMUsage,
    ProviderStatus,
    strip_reasoning,
)

logger = logging.getLogger("peerlens.llm.cli")

DETECT_TIMEOUT = 20.0


@dataclass
class StreamState:
    """Accumulates what a CLI reports over the course of one request."""

    text_parts: list[str] = field(default_factory=list)
    final_text: str | None = None
    model: str = ""
    usage: LLMUsage = field(default_factory=LLMUsage)

    @property
    def text(self) -> str:
        if self.final_text is not None:
            return self.final_text
        return "".join(self.text_parts)


def compose_prompt(system: str, user: str) -> str:
    """Fold the system prompt into the stdin message.

    Both CLIs are invoked with the prompt on stdin so that large research
    material never touches a command line. Keeping the system prompt in the
    same channel means one code path on Windows and Linux, with no argument
    length limit to worry about.
    """
    if not system:
        return user
    return (
        "# SYSTEM INSTRUCTIONS — follow these exactly\n\n"
        f"{system}\n\n"
        "# END OF SYSTEM INSTRUCTIONS\n\n"
        f"{user}"
    )


def workspace_dir() -> str:
    """An empty scratch directory, so the CLI never sees the PeerLens source."""
    path = config.DATA_DIR / "provider-workspace"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


class CLIProvider(LLMProvider):
    """Base class for CLI-backed providers."""

    #: Executable names to look for, in order.
    binary_names: tuple[str, ...] = ()
    label: str = ""
    install_hint: str = ""
    is_subscription = True

    # -- subclass hooks ----------------------------------------------------

    def build_args(self, request: AIRequest) -> list[str]:
        """CLI arguments for one request, excluding the executable itself."""
        raise NotImplementedError

    def parse_line(self, line: str, state: StreamState) -> Iterable[AIEvent]:
        raise NotImplementedError

    async def check_auth(self, launcher: process.Launcher) -> tuple[bool | None, str]:
        """Return ``(authenticated, message)``; ``None`` when not detectable."""
        return None, ""

    # -- detection ---------------------------------------------------------

    def launcher(self) -> process.Launcher | None:
        """Where this CLI lives: on PATH, or inside WSL on a Windows host."""
        return process.resolve_launcher(self.binary_names)

    def binary(self) -> str | None:
        launcher = self.launcher()
        return launcher.binary if launcher else None

    async def capture(self, launcher: process.Launcher, args: list[str]) -> tuple[int, str, str]:
        return await process.run_capture(launcher.argv(args), timeout=DETECT_TIMEOUT)

    async def version(self, launcher: process.Launcher) -> str:
        code, out, err = await self.capture(launcher, ["--version"])
        if code != 0:
            return ""
        return (out or err).strip().splitlines()[0] if (out or err).strip() else ""

    async def status(self) -> ProviderStatus:
        launcher = self.launcher()
        if launcher is None:
            return ProviderStatus(
                id=self.name,
                name=self.label or self.name,
                state="not_installed",
                installed=False,
                message=self.install_hint,
            )
        version = await self.version(launcher)
        authenticated, message = await self.check_auth(launcher)
        if authenticated is False:
            state = "not_authenticated"
        elif authenticated is True:
            state = "ready"
        else:
            # Not reliably detectable: assume usable and report honestly.
            state = "ready"
            message = message or "Authentication state is owned by the CLI and not reported."
        return ProviderStatus(
            id=self.name,
            name=self.label or self.name,
            state=state,
            message=message,
            installed=True,
            authenticated=authenticated,
            configured=True,
            version=f"{version} (WSL)" if launcher.mode == "wsl" and version else version,
            model=self.model,
        )

    # -- inference ---------------------------------------------------------

    async def run(self, request: AIRequest) -> AsyncIterator[AIEvent]:
        # Every request starts, whatever happens next: consumers can rely on it.
        yield AIEvent(type="start", request_id=request.request_id)

        launcher = self.launcher()
        if launcher is None:
            yield AIEvent(
                type="error",
                request_id=request.request_id,
                message=f"{self.label or self.name} is not installed. {self.install_hint}",
                code=ErrorCode.CLI_NOT_INSTALLED.value,
            )
            return

        workspace = workspace_dir()
        args = launcher.argv(self.build_args(request), cwd=workspace)
        stdin_data = compose_prompt(request.system_prompt, request.prompt)
        state = StreamState()
        logger.info(
            "%s request %s (%s): %s",
            self.name, request.request_id, request.task_type, process.join_for_log(args),
        )
        try:
            async for line in process.stream_lines(
                args,
                stdin_data=stdin_data,
                timeout=config.LLM_TIMEOUT_SECONDS,
                request_id=request.request_id,
                provider=self.label or self.name,
                task_type=request.task_type,
                paper_id=request.paper_id,
                cwd=workspace,
            ):
                for event in self.parse_line(line, state):
                    event.request_id = request.request_id
                    yield event
        except LLMError as exc:
            yield AIEvent(
                type="error", request_id=request.request_id, message=str(exc), code=exc.code
            )
            return

        text = strip_reasoning(state.text)
        if not text:
            yield AIEvent(
                type="error",
                request_id=request.request_id,
                message=f"{self.label or self.name} returned no output.",
                code=ErrorCode.PROCESS_FAILED.value,
            )
            return
        yield AIEvent(type="usage", request_id=request.request_id, usage=state.usage)
        yield AIEvent(
            type="complete",
            request_id=request.request_id,
            text=text,
            model=state.model or self.model,
            usage=state.usage,
        )

    async def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        max_tokens: int = 8000,
        temperature: float = 0.2,
        request: AIRequest | None = None,
    ) -> LLMResult:
        """Drain :meth:`run` into the single-shot result PeerLens works with."""
        req = request or AIRequest(
            prompt=user,
            system_prompt=system,
            json_mode=json_mode,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        started = time.perf_counter()
        text = ""
        model = self.model
        usage = LLMUsage()
        async for event in self.run(req):
            if event.type == "error":
                raise LLMError(event.message, event.code or ErrorCode.UNKNOWN_PROVIDER_ERROR)
            if event.type == "usage" and event.usage is not None:
                usage = event.usage
            elif event.type == "complete":
                text = event.text
                model = event.model or model
                if event.usage is not None:
                    usage = event.usage
        return LLMResult(
            text=text,
            provider=self.name,
            model=model,
            usage=usage,
            latency_ms=int((time.perf_counter() - started) * 1000),
            is_local=False,
        )

    async def complete_for(self, request: AIRequest) -> LLMResult:
        """Pass the request through so its id/paper reach the process registry."""
        return await self.complete(
            system=request.system_prompt,
            user=request.prompt,
            json_mode=request.json_mode,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            request=request,
        )

    async def cancel(self, request_id: str) -> bool:
        return process.cancel(request_id)
