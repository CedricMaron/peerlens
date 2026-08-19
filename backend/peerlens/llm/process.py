"""Tightly controlled subprocess execution for CLI-backed providers.

Rules enforced here:

* fixed binaries resolved from ``PATH``, never a user-supplied command;
* explicit argument arrays, never a shell string (``shell=True`` is never used);
* prompts travel on **stdin**, so research material never lands in a command
  line (also keeps PeerLens inside the Windows command-length limit);
* every process is registered so it can be cancelled, and terminated in a
  ``finally`` block so a dropped HTTP connection cannot leave a zombie.

There is deliberately no generic "run this command" entry point, and no HTTP
endpoint anywhere in PeerLens that accepts a command to execute.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Iterable, Sequence
from dataclasses import dataclass, field

from .errors import ErrorCode, LLMError

logger = logging.getLogger("peerlens.llm.process")

#: JSONL lines from a CLI can be large (a whole manuscript on one line).
STREAM_LIMIT = 8 * 1024 * 1024
STDERR_KEEP_CHARS = 4000


@dataclass(frozen=True)
class Launcher:
    """How to start a CLI: natively, or inside WSL from a Windows host."""

    binary: str
    mode: str = "native"  # "native" | "wsl"

    def argv(self, args: Sequence[str], cwd: str | None = None) -> list[str]:
        """The exact argument array to spawn.

        Native launches never involve a shell. The WSL launch has to go through
        ``bash -lc`` (that is how ``wsl.exe`` accepts a command), so every
        component is quoted with ``shlex.quote`` — and prompts still travel on
        stdin, never inside the command string.
        """
        if self.mode == "native":
            return [self.binary, *args]
        command = " ".join(shlex.quote(part) for part in [self.binary, *args])
        if cwd:
            command = f"cd {shlex.quote(to_wsl_path(cwd))} && {command}"
        return ["wsl", "bash", "-lc", command]


def to_wsl_path(path: str) -> str:
    """``C:\\Users\\me\\data`` -> ``/mnt/c/Users/me/data``."""
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", os.path.abspath(path))
    if not match:
        return path
    return f"/mnt/{match.group(1).lower()}/{match.group(2).replace(chr(92), '/')}"


def resolve_binary(names: Sequence[str]) -> str | None:
    """Path to the first available executable, or ``None``.

    ``shutil.which`` honours PATHEXT, so ``claude`` also resolves to
    ``claude.cmd``/``claude.exe`` on Windows.
    """
    launcher = resolve_launcher(names)
    return launcher.binary if launcher else None


def resolve_launcher(names: Sequence[str]) -> Launcher | None:
    """Find a CLI natively first, then inside WSL when running on Windows.

    Many Windows users install Claude Code or Codex inside WSL rather than on
    the host. Looking there is the difference between "not installed" and a
    working provider. The interactive-shell probe (``bash -ic``) additionally
    finds installs that only exist on a PATH set up by ``~/.bashrc`` (nvm).
    """
    for name in names:
        found = shutil.which(name)
        if found:
            return Launcher(found, "native")
    if sys.platform != "win32" or not shutil.which("wsl"):  # pragma: no cover - Windows only
        return None
    for name in names:  # pragma: no cover - Windows only
        for shell_flag in ("-lc", "-ic"):
            try:
                probe = subprocess.run(
                    ["wsl", "bash", shell_flag, f"command -v {shlex.quote(name)}"],
                    capture_output=True, text=True, timeout=10, check=False,
                    encoding="utf-8", errors="replace",
                )
            except (OSError, subprocess.SubprocessError):
                continue
            path = (probe.stdout or "").strip().splitlines()
            if probe.returncode == 0 and path and path[-1].startswith("/"):
                return Launcher(path[-1], "wsl")
    return None


def child_env() -> dict[str, str]:
    """Environment for CLI providers.

    The real environment is passed through because official CLIs need ``PATH``
    and ``HOME``/``USERPROFILE`` to locate the credentials they own. PeerLens
    adds nothing secret and reads no credential file itself.
    """
    env = dict(os.environ)
    env.setdefault("NO_COLOR", "1")
    env.setdefault("TERM", "dumb")
    return env


# --------------------------------------------------------------------------
# Active-request registry (cancellation)
# --------------------------------------------------------------------------

@dataclass
class ActiveRequest:
    request_id: str
    provider: str
    task_type: str
    paper_id: int | None
    started_at: float = field(default_factory=time.time)
    process: asyncio.subprocess.Process | None = None
    cancelled: bool = False
    terminating: asyncio.Future | None = None


_ACTIVE: dict[str, ActiveRequest] = {}


def active_requests() -> list[ActiveRequest]:
    return list(_ACTIVE.values())


async def terminate(proc: asyncio.subprocess.Process) -> None:
    """Stop a process and its children, on Windows and POSIX alike."""
    if proc.returncode is not None:
        return
    if sys.platform == "win32":  # pragma: no cover - platform specific
        # Node-based CLIs spawn children; taskkill /T removes the whole tree.
        taskkill = shutil.which("taskkill")
        if taskkill:
            with contextlib.suppress(Exception):
                killer = await asyncio.create_subprocess_exec(
                    taskkill, "/PID", str(proc.pid), "/T", "/F",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(killer.wait(), timeout=10)
    with contextlib.suppress(ProcessLookupError):
        proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(proc.wait(), timeout=5)


def cancel(request_id: str) -> bool:
    """Cancel one request. Unrelated requests are untouched."""
    record = _ACTIVE.get(request_id)
    if record is None:
        return False
    record.cancelled = True
    if record.process is not None:
        # The stream loop notices `cancelled` and awaits this before returning,
        # so no termination task outlives the request.
        record.terminating = asyncio.ensure_future(terminate(record.process))
    return True


def cancel_for_paper(paper_id: int) -> list[str]:
    """Cancel every in-flight CLI request for one research project."""
    return [r.request_id for r in active_requests() if r.paper_id == paper_id and cancel(r.request_id)]


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------

async def run_capture(
    argv: Sequence[str], timeout: float = 20.0, stdin_data: str | None = None
) -> tuple[int, str, str]:
    """Run a short, fixed command (``--version``, ``auth status``) and capture it.

    Returns ``(returncode, stdout, stderr)``. ``returncode`` is ``-1`` when the
    command could not be started or timed out.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE if stdin_data is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=child_env(),
            limit=STREAM_LIMIT,
        )
    except (OSError, ValueError) as exc:
        return -1, "", f"{type(exc).__name__}: {exc}"
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(stdin_data.encode() if stdin_data is not None else None),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        await terminate(proc)
        return -1, "", f"timed out after {timeout:.0f}s"
    return (
        proc.returncode or 0,
        out.decode("utf-8", errors="replace"),
        err.decode("utf-8", errors="replace"),
    )


async def stream_lines(
    argv: Sequence[str],
    *,
    stdin_data: str,
    timeout: float,
    request_id: str,
    provider: str,
    task_type: str = "general",
    paper_id: int | None = None,
    cwd: str | None = None,
) -> AsyncIterator[str]:
    """Run a CLI and yield its stdout lines.

    Raises a normalized :class:`LLMError` on timeout, cancellation or a
    non-zero exit. The process is always terminated on the way out, including
    when the consumer is cancelled (a dropped HTTP request).
    """
    record = ActiveRequest(
        request_id=request_id, provider=provider, task_type=task_type, paper_id=paper_id
    )
    _ACTIVE[request_id] = record

    proc: asyncio.subprocess.Process | None = None
    stderr_tail = ""
    try:
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=child_env(),
                limit=STREAM_LIMIT,
            )
        except (OSError, ValueError) as exc:
            raise LLMError(
                f"Could not start {provider}: {exc}", ErrorCode.PROCESS_FAILED
            ) from exc
        record.process = proc

        async def feed_stdin() -> None:
            assert proc is not None and proc.stdin is not None
            try:
                proc.stdin.write(stdin_data.encode())
                await proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                pass  # the CLI exited early; the exit code explains why
            finally:
                with contextlib.suppress(Exception):
                    proc.stdin.close()

        async def drain_stderr() -> str:
            assert proc is not None and proc.stderr is not None
            chunks: list[str] = []
            size = 0
            while True:
                chunk = await proc.stderr.read(4096)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                chunks.append(text)
                size += len(text)
                while size > STDERR_KEEP_CHARS and len(chunks) > 1:
                    size -= len(chunks.pop(0))
            return "".join(chunks)

        stdin_task = asyncio.ensure_future(feed_stdin())
        stderr_task = asyncio.ensure_future(drain_stderr())
        deadline = time.monotonic() + timeout

        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise LLMError(
                        f"{provider} did not finish within {timeout:.0f}s. Scientific "
                        "reviews send a large prompt; raise PEERLENS_LLM_TIMEOUT or "
                        "reduce the amount of research material.",
                        ErrorCode.REQUEST_TIMEOUT,
                    )
                assert proc.stdout is not None
                try:
                    raw = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
                except asyncio.TimeoutError:
                    raise LLMError(
                        f"{provider} did not finish within {timeout:.0f}s.",
                        ErrorCode.REQUEST_TIMEOUT,
                    ) from None
                except ValueError as exc:  # line longer than STREAM_LIMIT
                    raise LLMError(
                        f"{provider} emitted an oversized output line.",
                        ErrorCode.PROCESS_FAILED,
                        detail=str(exc),
                    ) from exc
                if not raw:
                    break
                if record.cancelled:
                    raise LLMError("Request cancelled.", ErrorCode.REQUEST_CANCELLED)
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    yield line

            returncode = await asyncio.wait_for(proc.wait(), timeout=30)
            stderr_tail = await _collect(stderr_task)
            if record.cancelled:
                raise LLMError("Request cancelled.", ErrorCode.REQUEST_CANCELLED)
            if returncode != 0:
                logger.warning("%s exited with code %s: %s", provider, returncode, stderr_tail[-800:])
                raise LLMError(
                    f"{provider} exited with code {returncode}.",
                    ErrorCode.PROCESS_FAILED,
                    detail=stderr_tail,
                )
        finally:
            stdin_task.cancel()
            if not stderr_task.done():
                stderr_task.cancel()
            with contextlib.suppress(Exception):
                await stdin_task
    finally:
        _ACTIVE.pop(request_id, None)
        if record.terminating is not None:
            with contextlib.suppress(Exception):
                await record.terminating
        if proc is not None:
            await terminate(proc)


async def _collect(task: asyncio.Future[str]) -> str:
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=5)
    except Exception:  # noqa: BLE001 - diagnostics only
        return ""


def join_for_log(argv: Iterable[str]) -> str:
    """Readable argv for logs. Prompts are never in argv, so nothing leaks."""
    return " ".join(argv)
