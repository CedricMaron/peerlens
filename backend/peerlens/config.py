"""Application paths and configuration.

PeerLens is local-first. All persistent state lives under a single data
directory (``/app/data`` inside the Docker image) so that replacing the
container never loses research.
"""

from __future__ import annotations

import os
from pathlib import Path


def _find_repo_root() -> Path:
    """Walk upwards looking for the repository layout (prompts/ + backend/)."""
    here = Path(__file__).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "prompts" / "checklist").is_dir():
            return candidate
    return here.parents[2]


REPO_ROOT = _find_repo_root()

DATA_DIR = Path(os.environ.get("PEERLENS_DATA_DIR") or (REPO_ROOT / "data")).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "peerlens.db"
DATABASE_URL = os.environ.get("PEERLENS_DATABASE_URL") or f"sqlite:///{DB_PATH}"

PROMPTS_DIR = Path(
    os.environ.get("PEERLENS_PROMPTS_DIR") or (REPO_ROOT / "prompts")
).resolve()

# The compiled React application, when present (Docker image / after a build).
STATIC_DIR = Path(
    os.environ.get("PEERLENS_STATIC_DIR") or (REPO_ROOT / "frontend" / "dist")
).resolve()

MAX_UPLOAD_BYTES = int(os.environ.get("PEERLENS_MAX_UPLOAD_BYTES", 25 * 1024 * 1024))

# Environment-variable provider configuration remains available for server
# deployments, but is never required: Settings -> AI Provider writes the same
# configuration into the database.
ENV_PROVIDER = os.environ.get("PEERLENS_AI_PROVIDER")
ENV_PROVIDER_CONFIG = {
    "openai": {
        "api_key": os.environ.get("OPENAI_API_KEY"),
        "model": os.environ.get("OPENAI_MODEL"),
        "base_url": os.environ.get("OPENAI_BASE_URL"),
    },
    "anthropic": {
        "api_key": os.environ.get("ANTHROPIC_API_KEY"),
        "model": os.environ.get("ANTHROPIC_MODEL"),
        "base_url": os.environ.get("ANTHROPIC_BASE_URL"),
    },
    "ollama": {
        "api_key": None,
        "model": os.environ.get("OLLAMA_MODEL"),
        "base_url": os.environ.get("OLLAMA_BASE_URL"),
    },
}

# Generous by default: local reasoning models on CPU can take many minutes per
# scientific review, and a timeout mid-analysis is worse than a slow answer.
LLM_TIMEOUT_SECONDS = float(os.environ.get("PEERLENS_LLM_TIMEOUT", 900))
OPENALEX_MAILTO = os.environ.get("PEERLENS_OPENALEX_MAILTO", "")


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
