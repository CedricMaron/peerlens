"""Settings -> AI Provider.

The API key is written to the server-side database and never sent back to the
browser: only a masked hint and a boolean are exposed. Account-backed providers
(Claude Code, Codex) have no key here at all — their credentials belong to the
official CLI, which PeerLens starts but never inspects.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..llm import process
from ..llm.base import ProviderConfig
from ..llm.login import login_manager
from ..llm.manager import provider_manager
from ..llm.providers import list_ollama_models
from ..schemas import (
    ActiveRequestOut,
    CancelResult,
    LoginStateOut,
    ProviderSettingsIn,
    ProviderSettingsOut,
    ProviderStatusList,
    ProviderStatusOut,
    TestConnectionRequest,
    TestConnectionResult,
)
from ..services import settings_service

router = APIRouter(tags=["settings"])


def _known(provider_id: str) -> None:
    if not provider_manager.has(provider_id):
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider_id}'.")


@router.get("/settings/provider", response_model=ProviderSettingsOut)
def read_provider(db: Session = Depends(get_db)):
    return settings_service.public_provider_settings(db)


@router.put("/settings/provider", response_model=ProviderSettingsOut)
def write_provider(payload: ProviderSettingsIn, db: Session = Depends(get_db)):
    _known(payload.provider)
    spec = provider_manager.spec(payload.provider)
    if spec.requires_model and not payload.model.strip():
        raise HTTPException(status_code=422, detail=f"{spec.label} requires a model.")
    settings_service.save_provider_config(
        db,
        payload.provider,
        payload.model.strip(),
        payload.api_key,
        payload.base_url,
        make_active=payload.make_active,
    )
    return settings_service.public_provider_settings(db)


@router.delete("/settings/provider/key", response_model=ProviderSettingsOut)
def delete_key(provider: str | None = None, db: Session = Depends(get_db)):
    settings_service.clear_api_key(db, provider)
    return settings_service.public_provider_settings(db)


@router.post("/settings/provider/test", response_model=TestConnectionResult)
async def test_connection(payload: TestConnectionRequest, db: Session = Depends(get_db)):
    """Test either the supplied draft settings or the saved ones."""
    stored = settings_service.get_provider_config(db)

    provider_name = payload.provider or (stored.provider if stored else None)
    if provider_name is None:
        return TestConnectionResult(
            ok=False, message="Choose a provider before testing the connection."
        )
    if not provider_manager.has(provider_name):
        return TestConnectionResult(ok=False, message=f"Unknown provider '{provider_name}'.")

    entry = settings_service.provider_entry(db, provider_name)
    api_key = payload.api_key or entry["api_key"]  # reuse the saved key without exposing it
    model = payload.model if payload.model is not None else entry["model"]
    base_url = payload.base_url or entry["base_url"]

    provider = provider_manager.get(
        ProviderConfig(
            provider=provider_name, model=model or "", api_key=api_key, base_url=base_url
        )
    )
    ok, message = await provider.test_connection()
    return TestConnectionResult(ok=ok, message=message)


# --------------------------------------------------------------------------
# Provider catalogue and status
# --------------------------------------------------------------------------

@router.get("/settings/providers", response_model=ProviderStatusList)
async def list_providers(db: Session = Depends(get_db)):
    """Every supported provider with its current, honestly-reported state."""
    active = settings_service.active_provider_id(db)
    rows: list[ProviderStatusOut] = []
    for spec in provider_manager.specs():
        entry = settings_service.provider_entry(db, spec.id)
        config = ProviderConfig(
            provider=spec.id,
            model=entry["model"],
            api_key=entry["api_key"],
            base_url=entry["base_url"],
        )
        status = await provider_manager.status(config)
        rows.append(
            ProviderStatusOut(
                id=spec.id,
                label=spec.label,
                kind=spec.kind,
                blurb=spec.blurb,
                setup_hint=spec.setup_hint,
                state=status.state,
                message=status.message,
                installed=status.installed,
                authenticated=status.authenticated,
                configured=status.configured,
                available=status.available,
                version=status.version,
                model=entry["model"] or "",
                needs_api_key=spec.needs_api_key,
                requires_model=spec.requires_model,
                supports_login=spec.supports_login,
                is_local=spec.is_local,
                is_subscription=spec.is_subscription,
                api_key_set=bool(entry["api_key"]),
                api_key_hint=entry["key_hint"],
                base_url=entry["base_url"] or "",
                is_active=spec.id == active,
            )
        )
    return ProviderStatusList(active_provider=active, providers=rows)


@router.post("/settings/providers/{provider_id}/select", response_model=ProviderSettingsOut)
def select_provider(provider_id: str, db: Session = Depends(get_db)):
    """Make a provider active. Research state is never touched by this."""
    _known(provider_id)
    settings_service.select_provider(db, provider_id)
    return settings_service.public_provider_settings(db)


# --------------------------------------------------------------------------
# Login flows owned by the official CLIs
# --------------------------------------------------------------------------

def _cli_provider(provider_id: str, db: Session):
    _known(provider_id)
    spec = provider_manager.spec(provider_id)
    if not spec.supports_login:
        raise HTTPException(
            status_code=400, detail=f"{spec.label} does not use an interactive login."
        )
    entry = settings_service.provider_entry(db, provider_id)
    return provider_manager.get(
        ProviderConfig(provider=provider_id, model=entry["model"] or "")
    )


@router.post("/settings/providers/{provider_id}/login", response_model=LoginStateOut)
async def start_login(provider_id: str, db: Session = Depends(get_db)):
    provider = _cli_provider(provider_id, db)
    session = await login_manager.start(provider_id, provider)
    return LoginStateOut(
        provider=provider_id,
        state=session.state,
        message=session.message,
        url=session.url,
        running=session.running,
    )


@router.get("/settings/providers/{provider_id}/login", response_model=LoginStateOut)
def login_state(provider_id: str):
    _known(provider_id)
    session = login_manager.state(provider_id)
    return LoginStateOut(
        provider=provider_id,
        state=session.state,
        message=session.message,
        url=session.url,
        running=session.running,
    )


@router.delete("/settings/providers/{provider_id}/login", response_model=LoginStateOut)
async def cancel_login(provider_id: str):
    _known(provider_id)
    session = await login_manager.cancel(provider_id)
    return LoginStateOut(
        provider=provider_id, state=session.state, message=session.message, running=False
    )


# --------------------------------------------------------------------------
# In-flight AI requests
# --------------------------------------------------------------------------

@router.get("/ai/requests", response_model=list[ActiveRequestOut])
def active_requests():
    now = time.time()
    return [
        ActiveRequestOut(
            request_id=r.request_id,
            provider=r.provider,
            task_type=r.task_type,
            paper_id=r.paper_id,
            running_for_ms=int((now - r.started_at) * 1000),
        )
        for r in process.active_requests()
    ]


@router.post("/ai/requests/{request_id}/cancel", response_model=CancelResult)
def cancel_request(request_id: str):
    """Cancel one request. Other in-flight requests keep running."""
    return CancelResult(cancelled=[request_id] if process.cancel(request_id) else [])


@router.post("/ai/papers/{paper_id}/cancel", response_model=CancelResult)
def cancel_paper_requests(paper_id: int):
    return CancelResult(cancelled=process.cancel_for_paper(paper_id))


@router.get("/settings/ollama/models", response_model=list[str])
async def ollama_models(base_url: str | None = None, db: Session = Depends(get_db)):
    """List models actually installed in the local Ollama instance."""
    if base_url is None:
        base_url = settings_service.provider_entry(db, "ollama")["base_url"]
    return await list_ollama_models(base_url)
