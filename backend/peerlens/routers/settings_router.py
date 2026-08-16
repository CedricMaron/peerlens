"""Settings -> AI Provider.

The API key is written to the server-side database and never sent back to the
browser: only a masked hint and a boolean are exposed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..llm.base import ProviderConfig
from ..llm.providers import PROVIDERS, list_ollama_models
from ..schemas import (
    ProviderSettingsIn,
    ProviderSettingsOut,
    TestConnectionRequest,
    TestConnectionResult,
)
from ..services import settings_service

router = APIRouter(tags=["settings"])


@router.get("/settings/provider", response_model=ProviderSettingsOut)
def read_provider(db: Session = Depends(get_db)):
    return settings_service.public_provider_settings(db)


@router.put("/settings/provider", response_model=ProviderSettingsOut)
def write_provider(payload: ProviderSettingsIn, db: Session = Depends(get_db)):
    settings_service.save_provider_config(
        db, payload.provider, payload.model, payload.api_key, payload.base_url
    )
    return settings_service.public_provider_settings(db)


@router.delete("/settings/provider/key", response_model=ProviderSettingsOut)
def delete_key(db: Session = Depends(get_db)):
    settings_service.clear_api_key(db)
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

    api_key = payload.api_key
    if not api_key and stored and stored.provider == provider_name:
        api_key = stored.api_key  # reuse the saved key without exposing it

    model = payload.model or (stored.model if stored and stored.provider == provider_name else "")
    model = model or settings_service.DEFAULT_MODELS.get(provider_name, "")
    base_url = payload.base_url or settings_service.DEFAULT_BASE_URLS.get(provider_name)
    if stored and stored.provider == provider_name and not payload.base_url:
        base_url = stored.base_url or base_url

    provider_cls = PROVIDERS.get(provider_name)
    if provider_cls is None:
        return TestConnectionResult(ok=False, message=f"Unknown provider '{provider_name}'.")

    provider = provider_cls(
        ProviderConfig(
            provider=provider_name, model=model, api_key=api_key, base_url=base_url
        )
    )
    ok, message = await provider.test_connection()
    return TestConnectionResult(ok=ok, message=message)


@router.get("/settings/ollama/models", response_model=list[str])
async def ollama_models(base_url: str | None = None, db: Session = Depends(get_db)):
    """List models actually installed in the local Ollama instance."""
    if base_url is None:
        stored = settings_service.get_provider_config(db)
        base_url = (
            stored.base_url
            if stored and stored.provider == "ollama"
            else settings_service.DEFAULT_BASE_URLS["ollama"]
        )
    return await list_ollama_models(base_url)
