"""Test fixtures.

Environment is configured before importing PeerLens so that the database and
data directory point at a throwaway location.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="peerlens-tests-"))
os.environ["PEERLENS_DATA_DIR"] = str(_TMP)
os.environ["PEERLENS_DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"

from peerlens import models  # noqa: E402
from peerlens.db import SessionLocal, engine, init_db  # noqa: E402
from peerlens.llm.base import LLMProvider, LLMResult, LLMUsage, ProviderConfig  # noqa: E402


@pytest.fixture()
def db():
    """A clean database per test."""
    models.Base.metadata.drop_all(bind=engine)
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):  # noqa: ARG001 - ordering dependency: db resets schema first
    from fastapi.testclient import TestClient

    from peerlens.main import app

    with TestClient(app) as test_client:
        yield test_client


class ScriptedProvider(LLMProvider):
    """A provider that returns canned JSON, so flows can be tested without a model."""

    name = "scripted"
    is_local = True

    def __init__(self, responses: list[str]):
        super().__init__(ProviderConfig(provider="scripted", model="scripted-1"))
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        max_tokens: int = 8000,
        temperature: float = 0.2,
    ) -> LLMResult:
        self.calls.append(
            {"system": system, "user": user, "json_mode": json_mode, "max_tokens": max_tokens}
        )
        text = self.responses.pop(0) if self.responses else "{}"
        return LLMResult(
            text=text,
            provider=self.name,
            model=self.model,
            usage=LLMUsage(input_tokens=100, output_tokens=50, cached_tokens=None),
            latency_ms=12,
            is_local=True,
        )


@pytest.fixture()
def scripted(monkeypatch):
    """Install a scripted provider in place of the configured one."""

    def install(responses: list[str]) -> ScriptedProvider:
        provider = ScriptedProvider(responses)
        monkeypatch.setattr("peerlens.llm.client.build_provider", lambda _db: provider)
        return provider

    return install
