"""Application settings, including AI provider credentials.

API keys are stored server-side in SQLite and never returned to the frontend
(only a masked hint), never logged, and never written to browser storage.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .. import config
from ..llm.base import ProviderConfig
from ..models import AppSetting

PROVIDER_KEY = "ai_provider"
PRICING_KEY = "pricing_overrides"

DEFAULT_MODELS = {
    "openai": "gpt-4.1",
    "anthropic": "claude-sonnet-4-5-20250929",
    "ollama": "llama3.1:8b",
}

DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "ollama": "http://localhost:11434",
}


def _get_raw(db: Session, key: str) -> dict:
    row = db.get(AppSetting, key)
    return dict(row.value or {}) if row else {}


def _set_raw(db: Session, key: str, value: dict) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()


def get_provider_config(db: Session) -> ProviderConfig | None:
    """Resolve the active provider: database first, environment as fallback."""
    stored = _get_raw(db, PROVIDER_KEY)
    provider = stored.get("provider") or config.ENV_PROVIDER
    if not provider:
        return None

    env = config.ENV_PROVIDER_CONFIG.get(provider, {})
    api_key = stored.get("api_key") or env.get("api_key")
    model = stored.get("model") or env.get("model") or DEFAULT_MODELS.get(provider, "")
    base_url = (
        stored.get("base_url") or env.get("base_url") or DEFAULT_BASE_URLS.get(provider)
    )
    if not model:
        return None
    return ProviderConfig(provider=provider, model=model, api_key=api_key, base_url=base_url)


def save_provider_config(
    db: Session,
    provider: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
) -> None:
    existing = _get_raw(db, PROVIDER_KEY)
    # An empty api_key field means "keep the stored key", not "erase it".
    if not api_key and existing.get("provider") == provider:
        api_key = existing.get("api_key")
    _set_raw(
        db,
        PROVIDER_KEY,
        {
            "provider": provider,
            "model": model,
            "api_key": api_key or None,
            "base_url": base_url or DEFAULT_BASE_URLS.get(provider),
        },
    )


def clear_api_key(db: Session) -> None:
    stored = _get_raw(db, PROVIDER_KEY)
    stored["api_key"] = None
    _set_raw(db, PROVIDER_KEY, stored)


def mask_key(api_key: str | None) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "•" * len(api_key)
    return f"{api_key[:3]}{'•' * 8}{api_key[-4:]}"


def public_provider_settings(db: Session) -> dict:
    """Everything the frontend is allowed to know about provider config."""
    stored = _get_raw(db, PROVIDER_KEY)
    resolved = get_provider_config(db)
    provider = stored.get("provider") or config.ENV_PROVIDER or ""
    env_key = bool((config.ENV_PROVIDER_CONFIG.get(provider) or {}).get("api_key"))
    return {
        "provider": provider,
        "model": resolved.model if resolved else stored.get("model", ""),
        "base_url": resolved.base_url if resolved else stored.get("base_url", ""),
        "api_key_hint": mask_key(stored.get("api_key")),
        "api_key_set": bool(stored.get("api_key")) or env_key,
        "from_environment": not stored.get("provider") and bool(config.ENV_PROVIDER),
        "configured": resolved is not None
        and (resolved.provider == "ollama" or bool(resolved.api_key)),
        "defaults": {"models": DEFAULT_MODELS, "base_urls": DEFAULT_BASE_URLS},
    }


def get_pricing_overrides(db: Session) -> dict:
    return _get_raw(db, PRICING_KEY)


def save_pricing_overrides(db: Session, overrides: dict) -> None:
    _set_raw(db, PRICING_KEY, overrides)
