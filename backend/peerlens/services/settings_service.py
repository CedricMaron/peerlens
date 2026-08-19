"""Application settings, including AI provider credentials.

API keys are stored server-side in SQLite and never returned to the frontend
(only a masked hint), never logged, and never written to browser storage.

Configuration is kept **per provider**, so switching from OpenAI to Claude Code
and back does not lose a stored key, a model choice or a base URL.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .. import config
from ..llm.base import ProviderConfig
from ..llm.manager import DEFAULT_BASE_URLS, DEFAULT_MODELS, provider_manager
from ..models import AppSetting

PROVIDER_KEY = "ai_provider"
PRICING_KEY = "pricing_overrides"

__all__ = [
    "DEFAULT_BASE_URLS",
    "DEFAULT_MODELS",
    "PRICING_KEY",
    "PROVIDER_KEY",
    "clear_api_key",
    "get_pricing_overrides",
    "get_provider_config",
    "mask_key",
    "provider_entry",
    "public_provider_settings",
    "save_pricing_overrides",
    "save_provider_config",
    "select_provider",
]


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


def _stored(db: Session) -> dict:
    """Read provider settings, migrating the original single-provider shape."""
    raw = _get_raw(db, PROVIDER_KEY)
    providers = dict(raw.get("providers") or {})
    active = raw.get("provider") or ""
    if not providers and active and ("model" in raw or "api_key" in raw):
        providers[active] = {
            "model": raw.get("model") or "",
            "api_key": raw.get("api_key"),
            "base_url": raw.get("base_url"),
        }
    return {"provider": active, "providers": providers}


def _write(db: Session, state: dict) -> None:
    _set_raw(db, PROVIDER_KEY, {"provider": state["provider"], "providers": state["providers"]})


def provider_entry(db: Session, provider_id: str) -> dict:
    """Stored settings for one provider, falling back to env then defaults."""
    state = _stored(db)
    entry = dict(state["providers"].get(provider_id) or {})
    env = config.ENV_PROVIDER_CONFIG.get(provider_id, {})
    return {
        "model": entry.get("model") or env.get("model") or DEFAULT_MODELS.get(provider_id, ""),
        "api_key": entry.get("api_key") or env.get("api_key"),
        "base_url": entry.get("base_url")
        or env.get("base_url")
        or DEFAULT_BASE_URLS.get(provider_id),
        "stored_key": bool(entry.get("api_key")),
        "key_hint": mask_key(entry.get("api_key")),
        "from_environment": not entry and bool(env.get("api_key") or env.get("model")),
    }


def active_provider_id(db: Session) -> str:
    return _stored(db)["provider"] or config.ENV_PROVIDER or ""


def resolve_config(db: Session, provider_id: str) -> ProviderConfig | None:
    """Build the configuration for one provider, or ``None`` if unusable."""
    if not provider_manager.has(provider_id):
        return None
    spec = provider_manager.spec(provider_id)
    entry = provider_entry(db, provider_id)
    if spec.requires_model and not entry["model"]:
        return None
    return ProviderConfig(
        provider=provider_id,
        model=entry["model"],
        api_key=entry["api_key"],
        base_url=entry["base_url"],
    )


def get_provider_config(db: Session) -> ProviderConfig | None:
    """Resolve the active provider: database first, environment as fallback."""
    provider = active_provider_id(db)
    if not provider:
        return None
    return resolve_config(db, provider)


def save_provider_config(
    db: Session,
    provider: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
    make_active: bool = True,
) -> None:
    """Store one provider's configuration.

    ``make_active=False`` configures a provider without switching to it: which
    provider your research is sent to changes only when you say so. It still
    becomes active when nothing else is configured yet, so first-time setup is
    a single step.
    """
    state = _stored(db)
    entry = dict(state["providers"].get(provider) or {})
    # An empty api_key field means "keep the stored key", not "erase it".
    entry["model"] = model
    entry["base_url"] = base_url or DEFAULT_BASE_URLS.get(provider)
    if api_key:
        entry["api_key"] = api_key
    state["providers"][provider] = entry
    if make_active or not state["provider"]:
        state["provider"] = provider
    _write(db, state)


def select_provider(db: Session, provider: str) -> None:
    """Make ``provider`` active without touching any stored credential.

    Switching providers never resets research state: readiness, sections,
    issues and manuscripts live in their own tables and are untouched here.
    """
    state = _stored(db)
    state["provider"] = provider
    state["providers"].setdefault(provider, {})
    _write(db, state)


def clear_api_key(db: Session, provider: str | None = None) -> None:
    state = _stored(db)
    target = provider or state["provider"]
    entry = dict(state["providers"].get(target) or {})
    entry["api_key"] = None
    state["providers"][target] = entry
    _write(db, state)


def mask_key(api_key: str | None) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "•" * len(api_key)
    return f"{api_key[:3]}{'•' * 8}{api_key[-4:]}"


def is_configured(db: Session, provider_id: str) -> bool:
    """Configured means "PeerLens has what it needs to try a request"."""
    if not provider_manager.has(provider_id):
        return False
    spec = provider_manager.spec(provider_id)
    entry = provider_entry(db, provider_id)
    if spec.requires_model and not entry["model"]:
        return False
    if spec.needs_api_key and not entry["api_key"]:
        return False
    return True


def public_provider_settings(db: Session) -> dict:
    """Everything the frontend is allowed to know about provider config."""
    provider = active_provider_id(db)
    entry = provider_entry(db, provider) if provider else {}
    spec = provider_manager.spec(provider) if provider_manager.has(provider) else None
    return {
        "provider": provider,
        "label": spec.label if spec else provider,
        "kind": spec.kind if spec else "",
        "is_local": bool(spec.is_local) if spec else False,
        "needs_api_key": bool(spec.needs_api_key) if spec else False,
        "requires_model": bool(spec.requires_model) if spec else False,
        "model": entry.get("model", "") if provider else "",
        "base_url": entry.get("base_url") or "" if provider else "",
        "api_key_hint": entry.get("key_hint", "") if provider else "",
        "api_key_set": bool(entry.get("api_key")) if provider else False,
        "from_environment": not _stored(db)["provider"] and bool(config.ENV_PROVIDER),
        "configured": bool(provider) and is_configured(db, provider),
        "defaults": {"models": DEFAULT_MODELS, "base_urls": DEFAULT_BASE_URLS},
    }


def get_pricing_overrides(db: Session) -> dict:
    return _get_raw(db, PRICING_KEY)


def save_pricing_overrides(db: Session, overrides: dict) -> None:
    _set_raw(db, PRICING_KEY, overrides)
