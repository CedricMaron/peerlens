"""Interactive CLI login, supervised rather than intercepted.

A local web app cannot treat ``claude auth login`` or ``codex login`` like an
HTTP request: the official tool opens a browser and owns the whole exchange.
PeerLens therefore starts the official command, watches the process, surfaces
any URL it prints, and reports the outcome. It never reads, proxies or stores
the credentials that flow through it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
from dataclasses import dataclass, field

from . import process
from .base import ProviderConfig

logger = logging.getLogger("peerlens.llm.login")

LOGIN_TIMEOUT_SECONDS = 600.0
_URL = re.compile(r"https?://[^\s\"']+")

STARTED = "LOGIN_STARTED"
SUCCESS = "LOGIN_SUCCESS"
FAILED = "LOGIN_FAILED"
CANCELLED = "LOGIN_CANCELLED"
ALREADY_RUNNING = "LOGIN_ALREADY_RUNNING"
NOT_INSTALLED = "CLI_NOT_INSTALLED"
IDLE = "IDLE"


@dataclass
class LoginSession:
    provider_id: str
    state: str
    message: str = ""
    url: str = ""
    started_at: float = field(default_factory=time.time)
    running: bool = False


class LoginManager:
    """One supervised login at a time per provider."""

    def __init__(self) -> None:
        self._sessions: dict[str, LoginSession] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def state(self, provider_id: str) -> LoginSession:
        return self._sessions.get(provider_id) or LoginSession(provider_id, IDLE)

    async def start(self, provider_id: str, provider) -> LoginSession:
        """Start the official login flow for ``provider`` (a CLI provider)."""
        current = self._sessions.get(provider_id)
        if current and current.running:
            return LoginSession(
                provider_id,
                ALREADY_RUNNING,
                "A login is already in progress. Complete it in your browser.",
                url=current.url,
                running=True,
            )

        login_args = tuple(getattr(provider, "login_args", ()) or ())
        launcher = provider.launcher()
        if launcher is None or not login_args:
            session = LoginSession(
                provider_id, NOT_INSTALLED, getattr(provider, "install_hint", "")
            )
            self._sessions[provider_id] = session
            return session

        try:
            argv = launcher.argv(list(login_args))
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=process.child_env(),
                limit=process.STREAM_LIMIT,
            )
        except (OSError, ValueError) as exc:
            session = LoginSession(provider_id, FAILED, f"Could not start the login: {exc}")
            self._sessions[provider_id] = session
            return session

        session = LoginSession(
            provider_id,
            STARTED,
            getattr(provider, "login_hint", "Complete the sign-in in your browser."),
            running=True,
        )
        self._sessions[provider_id] = session
        self._processes[provider_id] = proc
        self._tasks[provider_id] = asyncio.ensure_future(
            self._supervise(provider_id, provider, proc, session)
        )
        return session

    async def _supervise(
        self,
        provider_id: str,
        provider,
        proc: asyncio.subprocess.Process,
        session: LoginSession,
    ) -> None:
        tail: list[str] = []
        try:
            deadline = time.monotonic() + LOGIN_TIMEOUT_SECONDS
            assert proc.stdout is not None
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    await process.terminate(proc)
                    session.state = FAILED
                    session.message = "The login flow timed out."
                    return
                try:
                    raw = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
                except asyncio.TimeoutError:
                    continue
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                tail.append(line)
                del tail[:-10]
                if not session.url:
                    found = _URL.search(line)
                    if found:
                        session.url = found.group(0)
                        session.message = (
                            "Complete the sign-in in your browser. If it did not open "
                            "automatically, use the link below."
                        )
            returncode = await proc.wait()
        except asyncio.CancelledError:
            session.state = CANCELLED
            session.message = "Login cancelled."
            raise
        finally:
            session.running = False
            self._processes.pop(provider_id, None)

        if session.state == CANCELLED:
            return
        # Trust the official tool's own report rather than the exit code alone.
        launcher = provider.launcher()
        authenticated, message = (
            await provider.check_auth(launcher) if launcher else (False, "")
        )
        if authenticated:
            session.state = SUCCESS
            session.message = message or "Signed in."
            return
        if returncode == 0 and authenticated is None:
            session.state = SUCCESS
            session.message = "The login command completed."
            return
        session.state = FAILED
        session.message = _failure_message(tail, _login_command(provider))
        logger.info("%s login failed (rc=%s)", provider_id, returncode)

    async def cancel(self, provider_id: str) -> LoginSession:
        proc = self._processes.get(provider_id)
        session = self._sessions.get(provider_id)
        if proc is not None:
            await process.terminate(proc)
        task = self._tasks.get(provider_id)
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        cancelled = LoginSession(provider_id, CANCELLED, "Login cancelled.")
        if session is not None:
            session.state = CANCELLED
            session.running = False
            session.message = "Login cancelled."
        self._sessions[provider_id] = cancelled
        return cancelled


def _login_command(provider) -> str:
    name = (getattr(provider, "binary_names", ("",)) or ("",))[0]
    return " ".join([name, *(str(a) for a in getattr(provider, "login_args", ()))]).strip()


def _failure_message(tail: list[str], command: str) -> str:
    hint = (
        f"The login did not complete. Run `{command}` in a terminal on this machine "
        "if your environment cannot open a browser."
    )
    last = next((line for line in reversed(tail) if line), "")
    return f"{hint} ({last[:160]})" if last else hint


login_manager = LoginManager()


def provider_for_login(spec, config: ProviderConfig | None = None):
    """Build a provider instance suitable for a login/status check."""
    return spec.cls(config or ProviderConfig(provider=spec.id, model=""))
