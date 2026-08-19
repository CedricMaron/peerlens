"""The provider layer: registry, CLI providers, process control, and the rule
that no provider can touch research readiness or the manuscript gate.

No real account, API key or paid request is needed: CLI behaviour is simulated
with short Python subprocesses, which also exercises the real process plumbing
on both Windows and Linux.
"""

from __future__ import annotations

import asyncio
import json
import sys

import pytest

from peerlens.llm import process
from peerlens.llm.base import AIRequest, ErrorCode, LLMError, ProviderConfig
from peerlens.llm.claude_code import ClaudeCodeProvider
from peerlens.llm.cli_provider import compose_prompt
from peerlens.llm.codex_cli import CodexProvider
from peerlens.llm.manager import ProviderManager, provider_manager
from peerlens.llm.providers import AnthropicProvider, OllamaProvider, OpenAIProvider
from peerlens.services import settings_service

# --------------------------------------------------------------------------
# Registration and selection
# --------------------------------------------------------------------------

def test_all_five_providers_are_registered():
    assert provider_manager.ids() == ["claude-code", "codex", "anthropic", "openai", "ollama"]


def test_registry_maps_each_id_to_its_implementation():
    expected = {
        "claude-code": ClaudeCodeProvider,
        "codex": CodexProvider,
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
    }
    for provider_id, cls in expected.items():
        assert provider_manager.spec(provider_id).cls is cls


def test_get_builds_the_selected_provider():
    provider = provider_manager.get(ProviderConfig(provider="ollama", model="qwen3:8b"))
    assert isinstance(provider, OllamaProvider)
    assert provider.is_local is True


def test_unknown_provider_is_rejected_with_a_code():
    with pytest.raises(LLMError) as exc:
        provider_manager.get(ProviderConfig(provider="not-a-provider", model="x"))
    assert exc.value.code == ErrorCode.UNKNOWN_PROVIDER.value


def test_a_new_provider_needs_no_changes_elsewhere():
    """The registry is the extension point."""
    manager = ProviderManager()
    before = len(manager.ids())
    manager.register(
        provider_manager.spec("ollama").__class__(
            id="demo", label="Demo", cls=OllamaProvider, kind="local", blurb="", is_local=True
        )
    )
    assert len(manager.ids()) == before + 1
    assert manager.has("demo")


def test_api_key_only_required_by_api_providers():
    needs_key = {s.id for s in provider_manager.specs() if s.needs_api_key}
    assert needs_key == {"openai", "anthropic"}


# --------------------------------------------------------------------------
# Settings: selection, per-provider storage, no-provider state
# --------------------------------------------------------------------------

def test_no_provider_state_lists_every_option(db):
    from peerlens.llm import client

    assert settings_service.get_provider_config(db) is None
    with pytest.raises(LLMError) as exc:
        client.build_provider(db)
    message = str(exc.value)
    assert exc.value.code == ErrorCode.NOT_CONFIGURED.value
    for name in ("Claude Code", "OpenAI Codex", "Anthropic API", "OpenAI API", "Ollama"):
        assert name in message


def test_switching_providers_keeps_each_configuration(db):
    settings_service.save_provider_config(db, "openai", "gpt-4.1", "sk-test-key", None)
    settings_service.save_provider_config(db, "ollama", "qwen3:8b", None, None)
    settings_service.select_provider(db, "claude-code")

    assert settings_service.active_provider_id(db) == "claude-code"
    # The OpenAI key survived two provider switches.
    assert settings_service.provider_entry(db, "openai")["api_key"] == "sk-test-key"
    assert settings_service.provider_entry(db, "ollama")["model"] == "qwen3:8b"

    settings_service.select_provider(db, "openai")
    config = settings_service.get_provider_config(db)
    assert (config.provider, config.model, config.api_key) == ("openai", "gpt-4.1", "sk-test-key")


def test_account_backed_providers_need_no_api_key_or_model(db):
    settings_service.select_provider(db, "claude-code")
    config = settings_service.get_provider_config(db)
    assert config is not None
    assert config.api_key is None
    assert config.model == ""
    assert settings_service.is_configured(db, "claude-code") is True


def test_api_key_is_never_returned_to_the_frontend(db):
    settings_service.save_provider_config(db, "anthropic", "claude-sonnet-4-5", "sk-ant-secret", None)
    public = settings_service.public_provider_settings(db)
    assert "sk-ant-secret" not in json.dumps(public)
    assert public["api_key_set"] is True
    assert public["api_key_hint"].startswith("sk-")


def test_legacy_single_provider_settings_are_migrated(db):
    from peerlens.models import AppSetting

    db.add(
        AppSetting(
            key=settings_service.PROVIDER_KEY,
            value={"provider": "openai", "model": "gpt-4o", "api_key": "sk-old", "base_url": None},
        )
    )
    db.commit()
    config = settings_service.get_provider_config(db)
    assert (config.provider, config.model, config.api_key) == ("openai", "gpt-4o", "sk-old")


# --------------------------------------------------------------------------
# CLI detection
# --------------------------------------------------------------------------
async def _wait_until(condition, timeout: float = 15.0, what: str = "condition") -> None:
    """Poll until ``condition()`` holds. Subprocess start-up time varies with load."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if condition():
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"Timed out waiting for {what}")



def _patch_cli(monkeypatch, binary: str | None, responses: dict[str, tuple[int, str, str]]):
    """Simulate an installed/missing CLI and its short informational commands."""
    launcher = process.Launcher(binary, "native") if binary else None
    monkeypatch.setattr(process, "resolve_launcher", lambda names: launcher)
    monkeypatch.setattr("peerlens.llm.cli_provider.process.resolve_launcher", lambda names: launcher)

    async def fake_capture(argv, timeout=20.0, stdin_data=None):
        key = " ".join(argv[1:])
        return responses.get(key, (1, "", "unexpected command"))

    monkeypatch.setattr("peerlens.llm.cli_provider.process.run_capture", fake_capture)


async def test_claude_cli_detected_and_authenticated(monkeypatch):
    _patch_cli(
        monkeypatch,
        "/usr/bin/claude",
        {
            "--version": (0, "2.1.233 (Claude Code)\n", ""),
            "auth status --json": (
                0,
                json.dumps({"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": "pro"}),
                "",
            ),
        },
    )
    status = await ClaudeCodeProvider(ProviderConfig(provider="claude-code", model="")).status()
    assert status.state == "ready"
    assert status.installed is True
    assert status.authenticated is True
    assert "2.1.233" in status.version
    # Subscription tiers are never inferred or displayed.
    assert "pro" not in status.message.lower()


async def test_claude_cli_installed_but_not_signed_in(monkeypatch):
    _patch_cli(
        monkeypatch,
        "/usr/bin/claude",
        {
            "--version": (0, "2.1.233", ""),
            "auth status --json": (0, json.dumps({"loggedIn": False}), ""),
        },
    )
    status = await ClaudeCodeProvider(ProviderConfig(provider="claude-code", model="")).status()
    assert status.state == "not_authenticated"
    assert status.authenticated is False


async def test_codex_cli_detection(monkeypatch):
    _patch_cli(
        monkeypatch,
        "/usr/bin/codex",
        {
            "--version": (0, "codex-cli 0.20.0", ""),
            "login status": (0, "Logged in using ChatGPT", ""),
        },
    )
    status = await CodexProvider(ProviderConfig(provider="codex", model="")).status()
    assert (status.installed, status.authenticated, status.state) == (True, True, "ready")


async def test_codex_not_logged_in(monkeypatch):
    _patch_cli(
        monkeypatch,
        "/usr/bin/codex",
        {"--version": (0, "codex-cli 0.20.0", ""), "login status": (1, "Not logged in", "")},
    )
    status = await CodexProvider(ProviderConfig(provider="codex", model="")).status()
    assert status.state == "not_authenticated"


async def test_missing_cli_is_reported_not_crashed(monkeypatch):
    _patch_cli(monkeypatch, None, {})
    for cls in (ClaudeCodeProvider, CodexProvider):
        provider = cls(ProviderConfig(provider=cls.name, model=""))
        status = await provider.status()
        assert status.state == "not_installed"
        assert status.installed is False
        assert status.message  # installation guidance, not a silent failure


async def test_missing_cli_request_yields_a_normalized_error(monkeypatch):
    _patch_cli(monkeypatch, None, {})
    provider = ClaudeCodeProvider(ProviderConfig(provider="claude-code", model=""))
    events = [e async for e in provider.run(AIRequest(prompt="hello"))]
    assert [e.type for e in events] == ["start", "error"]
    assert events[-1].code == ErrorCode.CLI_NOT_INSTALLED.value
    with pytest.raises(LLMError) as exc:
        await provider.complete(system="", user="hello")
    assert exc.value.code == ErrorCode.CLI_NOT_INSTALLED.value


# --------------------------------------------------------------------------
# Login flow
# --------------------------------------------------------------------------

async def test_login_reports_cli_not_installed(monkeypatch):
    from peerlens.llm.login import NOT_INSTALLED, LoginManager

    _patch_cli(monkeypatch, None, {})
    provider = CodexProvider(ProviderConfig(provider="codex", model=""))
    session = await LoginManager().start("codex", provider)
    assert session.state == NOT_INSTALLED
    assert session.message  # installation guidance


async def test_login_lifecycle_and_already_running(monkeypatch):
    """A supervised login publishes its URL and reports success on completion."""
    from peerlens.llm import login as login_module

    script = (
        "import sys, time;"
        "print('Open this URL: https://auth.example.test/device');"
        "sys.stdout.flush(); time.sleep(0.4)"
    )

    class FakeLoginProvider(CodexProvider):
        binary_names = ("python",)
        login_args = ("-c", script)

        def launcher(self):
            return process.Launcher(sys.executable, "native")

        async def check_auth(self, launcher):
            return True, "Connected."

    manager = login_module.LoginManager()
    provider = FakeLoginProvider(ProviderConfig(provider="codex", model=""))

    first = await manager.start("codex", provider)
    assert first.state == login_module.STARTED

    second = await manager.start("codex", provider)
    assert second.state == login_module.ALREADY_RUNNING

    await _wait_until(
        lambda: not manager.state("codex").running, what="the login process to finish"
    )
    final = manager.state("codex")
    assert final.state == login_module.SUCCESS
    assert final.url == "https://auth.example.test/device"


async def test_login_can_be_cancelled():
    from peerlens.llm import login as login_module

    class SlowLoginProvider(CodexProvider):
        binary_names = ("python",)
        login_args = ("-c", "import time; time.sleep(30)")

        def launcher(self):
            return process.Launcher(sys.executable, "native")

        async def check_auth(self, launcher):
            return False, "not connected"

    manager = login_module.LoginManager()
    await manager.start("codex", SlowLoginProvider(ProviderConfig(provider="codex", model="")))
    session = await manager.cancel("codex")
    assert session.state == login_module.CANCELLED
    assert manager.state("codex").running is False


# --------------------------------------------------------------------------
# Event parsing: the same normalized shape for every provider
# --------------------------------------------------------------------------

CLAUDE_STREAM = [
    json.dumps({"type": "system", "subtype": "init", "model": "claude-sonnet-5", "tools": []}),
    json.dumps(
        {"type": "assistant", "message": {"content": [{"type": "text", "text": '{"status":'}]}}
    ),
    json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": '{"status": "ready"}',
            "usage": {
                "input_tokens": 12,
                "cache_read_input_tokens": 3000,
                "cache_creation_input_tokens": 100,
                "output_tokens": 40,
            },
            "duration_ms": 1591,
        }
    ),
]


def _cli_provider_running(cls, lines: list[str], exit_code: int = 0, delay: float = 0.0):
    """A provider whose 'CLI' is a short Python script printing ``lines``."""
    payload = json.dumps(lines)

    class Fake(cls):
        def launcher(self):
            return process.Launcher(sys.executable, "native")

        def build_args(self, request: AIRequest) -> list[str]:
            script = (
                "import json,sys,time;"
                f"lines=json.loads({payload!r});"
                "sys.stdin.read();"
                f"time.sleep({delay});"
                "[print(line, flush=True) for line in lines];"
                f"sys.exit({exit_code})"
            )
            return ["-c", script]

    return Fake(ProviderConfig(provider=cls.name, model=""))


async def test_claude_stream_json_is_normalized(tmp_path, monkeypatch):
    monkeypatch.setattr("peerlens.llm.cli_provider.workspace_dir", lambda: str(tmp_path))
    provider = _cli_provider_running(ClaudeCodeProvider, CLAUDE_STREAM)
    events = [e async for e in provider.run(AIRequest(prompt="analyse this"))]
    kinds = [e.type for e in events]

    assert kinds[0] == "start" and kinds[-1] == "complete"
    assert "status" in kinds and "text_delta" in kinds and "usage" in kinds
    final = events[-1]
    assert final.text == '{"status": "ready"}'
    assert final.model == "claude-sonnet-5"
    # Reported usage is passed through untouched; nothing is estimated.
    assert final.usage.input_tokens == 12 + 3000 + 100
    assert final.usage.output_tokens == 40
    assert final.usage.cached_tokens == 3000


async def test_claude_error_result_is_classified(tmp_path, monkeypatch):
    monkeypatch.setattr("peerlens.llm.cli_provider.workspace_dir", lambda: str(tmp_path))
    stream = [
        json.dumps(
            {
                "type": "result",
                "subtype": "error_during_execution",
                "is_error": True,
                "errors": ["rate limit exceeded"],
            }
        )
    ]
    provider = _cli_provider_running(ClaudeCodeProvider, stream)
    with pytest.raises(LLMError) as exc:
        await provider.complete(system="", user="x")
    assert exc.value.code == ErrorCode.RATE_LIMITED.value


@pytest.mark.parametrize(
    "stream",
    [
        # Older Codex event vocabulary.
        [
            json.dumps({"id": "0", "msg": {"type": "agent_message_delta", "delta": '{"ok":'}}),
            json.dumps({"id": "0", "msg": {"type": "agent_message", "message": '{"ok": true}'}}),
            json.dumps(
                {
                    "id": "0",
                    "msg": {
                        "type": "token_count",
                        "info": {"total_token_usage": {"input_tokens": 90, "output_tokens": 7}},
                    },
                }
            ),
        ],
        # Newer typed events.
        [
            json.dumps({"type": "thread.started", "thread_id": "t1"}),
            json.dumps(
                {"type": "item.completed", "item": {"type": "agent_message", "text": '{"ok": true}'}}
            ),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 90, "output_tokens": 7}}),
        ],
    ],
    ids=["legacy", "typed"],
)
async def test_codex_events_are_normalized(stream, tmp_path, monkeypatch):
    monkeypatch.setattr("peerlens.llm.cli_provider.workspace_dir", lambda: str(tmp_path))
    provider = _cli_provider_running(CodexProvider, stream)
    result = await provider.complete(system="be exact", user="hello")
    assert result.text == '{"ok": true}'
    assert (result.usage.input_tokens, result.usage.output_tokens) == (90, 7)


def test_codex_arguments_are_read_only_and_non_interactive():
    args = CodexProvider(ProviderConfig(provider="codex", model="o4-mini")).build_args(
        AIRequest(prompt="x")
    )
    assert args[:2] == ["exec", "--json"]
    assert "--sandbox" in args and args[args.index("--sandbox") + 1] == "read-only"
    assert args[-1] == "-"  # the prompt is read from stdin, never from argv


def test_claude_arguments_disable_every_tool():
    args = ClaudeCodeProvider(ProviderConfig(provider="claude-code", model="")).build_args(
        AIRequest(prompt="x")
    )
    assert args[args.index("--tools") + 1] == ""  # no edits, no shell, no file access
    assert "--safe-mode" in args  # no hooks, skills, plugins or CLAUDE.md
    assert "--strict-mcp-config" in args
    assert "--print" in args and "stream-json" in args


def test_research_material_never_reaches_the_command_line():
    """Prompts go on stdin: nothing to quote, nothing to leak into a process list."""
    request = AIRequest(prompt="SECRET UNPUBLISHED RESULT", system_prompt="rules")
    for cls in (ClaudeCodeProvider, CodexProvider):
        args = cls(ProviderConfig(provider=cls.name, model="")).build_args(request)
        assert not any("SECRET" in arg for arg in args)
    assert "SECRET UNPUBLISHED RESULT" in compose_prompt("rules", request.prompt)


# --------------------------------------------------------------------------
# Process control: failure, timeout, cancellation
# --------------------------------------------------------------------------

async def test_process_failure_is_normalized(tmp_path, monkeypatch):
    monkeypatch.setattr("peerlens.llm.cli_provider.workspace_dir", lambda: str(tmp_path))
    provider = _cli_provider_running(ClaudeCodeProvider, [], exit_code=3)
    with pytest.raises(LLMError) as exc:
        await provider.complete(system="", user="x")
    assert exc.value.code == ErrorCode.PROCESS_FAILED.value


async def test_timeout_is_normalized():
    script = "import time; time.sleep(20)"
    with pytest.raises(LLMError) as exc:
        async for _ in process.stream_lines(
            [sys.executable, "-c", script],
            stdin_data="",
            timeout=0.5,
            request_id="req-timeout",
            provider="fake",
        ):
            pass
    assert exc.value.code == ErrorCode.REQUEST_TIMEOUT.value
    assert process.active_requests() == []  # no zombie left behind


async def test_cancelling_one_request_leaves_others_running():
    slow = "import sys,time; print('started', flush=True); time.sleep(20)"
    quick = "import sys,time; time.sleep(0.4); print('done', flush=True)"

    async def run(script: str, request_id: str) -> list[str]:
        return [
            line
            async for line in process.stream_lines(
                [sys.executable, "-c", script],
                stdin_data="",
                timeout=30,
                request_id=request_id,
                provider="fake",
                paper_id=7 if request_id == "cancel-me" else 8,
            )
        ]

    cancelled_task = asyncio.ensure_future(run(slow, "cancel-me"))
    other_task = asyncio.ensure_future(run(quick, "keep-me"))

    await _wait_until(
        lambda: any(r.request_id == "cancel-me" for r in process.active_requests()),
        what="the slow request to register",
    )
    assert process.cancel("cancel-me") is True

    with pytest.raises(LLMError) as exc:
        await cancelled_task
    assert exc.value.code == ErrorCode.REQUEST_CANCELLED.value
    assert await other_task == ["done"]
    assert process.active_requests() == []


async def test_cancel_by_paper_only_touches_that_paper():
    script = "import time; print('x', flush=True); time.sleep(20)"

    async def run(request_id: str, paper_id: int):
        async for _ in process.stream_lines(
            [sys.executable, "-c", script],
            stdin_data="",
            timeout=30,
            request_id=request_id,
            provider="fake",
            paper_id=paper_id,
        ):
            pass

    tasks = [
        asyncio.ensure_future(run("paper-1-req", 1)),
        asyncio.ensure_future(run("paper-2-req", 2)),
    ]
    await _wait_until(
        lambda: len(process.active_requests()) == 2, what="both requests to register"
    )

    assert process.cancel_for_paper(1) == ["paper-1-req"]
    with pytest.raises(LLMError):
        await tasks[0]
    assert {r.request_id for r in process.active_requests()} == {"paper-2-req"}

    process.cancel("paper-2-req")
    with pytest.raises(LLMError):
        await tasks[1]


def test_cancelling_an_unknown_request_is_harmless():
    assert process.cancel("never-existed") is False


# --------------------------------------------------------------------------
# The existing HTTP providers still work
# --------------------------------------------------------------------------

def _fake_post(monkeypatch, payload: dict, status: int = 200):
    import httpx

    async def post(self, url, **kwargs):  # noqa: ANN001, ARG001
        return httpx.Response(status, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr("httpx.AsyncClient.post", post)


async def test_openai_provider_reports_its_own_usage(monkeypatch):
    _fake_post(
        monkeypatch,
        {
            "model": "gpt-4.1-2025-04-14",
            "choices": [{"message": {"content": '{"status": "ready"}'}}],
            "usage": {
                "prompt_tokens": 1200,
                "completion_tokens": 300,
                "prompt_tokens_details": {"cached_tokens": 800},
            },
        },
    )
    provider = OpenAIProvider(ProviderConfig(provider="openai", model="gpt-4.1", api_key="sk-x"))
    result = await provider.complete(system="s", user="u", json_mode=True)
    assert result.text == '{"status": "ready"}'
    assert (result.usage.input_tokens, result.usage.output_tokens) == (1200, 300)
    assert result.usage.cached_tokens == 800
    assert result.is_local is False


async def test_anthropic_provider_restores_prefilled_json(monkeypatch):
    _fake_post(
        monkeypatch,
        {
            "model": "claude-sonnet-4-5-20250929",
            "content": [{"type": "text", "text": '"status": "ready"}'}],
            "usage": {"input_tokens": 900, "output_tokens": 120, "cache_read_input_tokens": 400},
        },
    )
    provider = AnthropicProvider(
        ProviderConfig(provider="anthropic", model="claude-sonnet-4-5", api_key="sk-ant-x")
    )
    result = await provider.complete(system="s", user="u", json_mode=True)
    assert result.text.startswith("{")
    assert result.usage.input_tokens == 1300  # reported input + cache reads


async def test_ollama_provider_stays_local(monkeypatch):
    _fake_post(
        monkeypatch,
        {
            "model": "qwen3:8b",
            "message": {"content": "<think>hmm</think>\n{\"status\": \"ready\"}"},
            "prompt_eval_count": 500,
            "eval_count": 80,
        },
    )
    provider = OllamaProvider(ProviderConfig(provider="ollama", model="qwen3:8b"))
    result = await provider.complete(system="s", user="u", json_mode=True)
    assert result.is_local is True
    assert "<think>" not in result.text  # internal monologue never reaches the UI
    assert (result.usage.input_tokens, result.usage.output_tokens) == (500, 80)


async def test_api_key_errors_are_classified(monkeypatch):
    _fake_post(monkeypatch, {"error": {"message": "Incorrect API key"}}, status=401)
    provider = OpenAIProvider(ProviderConfig(provider="openai", model="gpt-4.1", api_key="bad"))
    with pytest.raises(LLMError) as exc:
        await provider.complete(system="s", user="u")
    assert exc.value.code == ErrorCode.INVALID_API_KEY.value


async def test_missing_api_key_is_not_a_crash():
    provider = AnthropicProvider(ProviderConfig(provider="anthropic", model="claude-sonnet-4-5"))
    with pytest.raises(LLMError) as exc:
        await provider.complete(system="s", user="u")
    assert exc.value.code == ErrorCode.NOT_CONFIGURED.value


def test_subscription_providers_report_unknown_cost_not_zero():
    from peerlens.llm import pricing

    assert pricing.estimate_cost("claude-code", "claude-sonnet-5", 5000, 900) is None
    assert pricing.estimate_cost("codex", "gpt-5-codex", 5000, 900) is None
    # Local inference genuinely costs nothing per token.
    assert pricing.estimate_cost("ollama", "qwen3:8b", 5000, 900, is_local=True) == 0.0


# --------------------------------------------------------------------------
# Routing: PeerLens asks the manager, and never falls back on its own
# --------------------------------------------------------------------------

def test_requests_are_routed_to_the_selected_provider(db):
    from peerlens.llm import client

    settings_service.save_provider_config(db, "openai", "gpt-4.1", "sk-x", None)
    assert isinstance(client.build_provider(db), OpenAIProvider)

    settings_service.select_provider(db, "claude-code")
    assert isinstance(client.build_provider(db), ClaudeCodeProvider)

    settings_service.select_provider(db, "ollama")
    settings_service.save_provider_config(db, "ollama", "qwen3:8b", None, None)
    assert isinstance(client.build_provider(db), OllamaProvider)


async def test_a_failing_provider_never_falls_back_to_another(db, monkeypatch):
    """Unpublished research must not be re-sent to a different vendor."""
    from peerlens.llm import client

    settings_service.save_provider_config(db, "openai", "gpt-4.1", "sk-x", None)
    _fake_post(monkeypatch, {"error": {"message": "Incorrect API key"}}, status=401)

    with pytest.raises(LLMError) as exc:
        await client.run_text(db, operation="general", system="s", user="u")
    assert exc.value.code == ErrorCode.INVALID_API_KEY.value

    # The failure is recorded against the provider that actually ran, and no
    # second provider was tried.
    from peerlens.models import AIUsageEvent

    events = db.query(AIUsageEvent).all()
    assert [e.provider for e in events] == ["openai"]
    assert events[0].success is False


def test_task_types_are_classified_for_reporting():
    from peerlens.llm.client import task_type_for

    assert task_type_for("extract:hypothesis") == "check_section"
    assert task_type_for("review:results") == "check_section"
    assert task_type_for("challenge") == "challenge_research"
    assert task_type_for("compile_manuscript") == "compile_manuscript"
    assert task_type_for("literature_analysis") == "paper_analysis"
    assert task_type_for("something_else") == "general"
