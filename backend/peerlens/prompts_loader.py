"""Loads and composes the scientific prompts from ``prompts/``.

Prompts are plain Markdown on disk so they can be reviewed, diffed and improved
independently of the code -- prompt quality is the product's core asset.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .config import PROMPTS_DIR
from .sections import SECTION_BY_KEY


class PromptNotFound(FileNotFoundError):
    pass


@lru_cache(maxsize=128)
def _read(relative: str) -> str:
    path = (PROMPTS_DIR / relative).resolve()
    if not path.is_file():
        raise PromptNotFound(f"Prompt file missing: {path}")
    return path.read_text(encoding="utf-8").strip()


def clear_cache() -> None:
    """Used by tests and by prompt iteration during development."""
    _read.cache_clear()


def shared_rules() -> str:
    return _read("shared/scientific_rules.md")


def section_prompt(section_key: str, kind: str) -> str:
    """Compose the full system prompt for a section extraction or review."""
    if section_key not in SECTION_BY_KEY:
        raise PromptNotFound(f"Unknown checklist section: {section_key}")
    if kind not in ("extract", "review"):
        raise ValueError(f"kind must be 'extract' or 'review', got {kind!r}")

    task_rules = _read(
        "shared/extraction_rules.md" if kind == "extract" else "shared/review_rules.md"
    )
    specific = _read(f"checklist/{section_key}/{kind}.md")
    section = SECTION_BY_KEY[section_key]
    header = (
        f"# Current task: {kind.upper()} — section {section.number}. {section.title}\n\n"
        f"Purpose of this section: {section.purpose}"
    )
    return "\n\n---\n\n".join([shared_rules(), task_rules, header, specific])


def global_prompt(name: str) -> str:
    """Compose a cross-cutting prompt (challenge, manuscript, literature)."""
    return "\n\n---\n\n".join([shared_rules(), _read(f"global/{name}.md")])


def available_prompts() -> dict[str, list[str]]:
    """Introspection used by the prompt-coverage test and the evals harness."""
    base = Path(PROMPTS_DIR)
    return {
        "checklist": sorted(
            f"{p.parent.name}/{p.name}" for p in base.glob("checklist/*/*.md")
        ),
        "global": sorted(p.name for p in base.glob("global/*.md")),
        "shared": sorted(p.name for p in base.glob("shared/*.md")),
    }
