"""Extraction, section review, and Challenge My Research.

The flow this module implements is the product:

    add research -> understand -> checklist -> review -> weaknesses
    -> correct -> re-check -> challenge
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai_schemas import ChallengeResult, ExtractionResult, ReviewResult
from ..llm import client
from ..models import Issue, PaperProject, ResearchInput, utcnow
from ..prompts_loader import global_prompt, section_prompt
from ..sections import (
    SECTION_BY_KEY,
    SECTION_KEYS,
    SectionStatus,
    Severity,
    normalize_section_key,
)
from . import research_state

logger = logging.getLogger("peerlens.analysis")

BLOCKING_SEVERITIES = {Severity.BLOCKER.value, Severity.MAJOR.value}


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def _extraction_user_message(db: Session, paper: PaperProject, section_key: str) -> str:
    definition = SECTION_BY_KEY[section_key]
    return "\n\n".join(
        [
            research_state.paper_context_header(paper),
            "# Research inputs available\n" + research_state.render_input_index(db, paper.id),
            "# Current Research State (other sections, for label consistency)\n"
            + research_state.render_full_state(db, paper.id, include_relationships=False),
            "# Existing understanding of this section\n"
            + research_state.render_section_state(db, paper.id, section_key),
            "# Research material (verbatim)\n"
            + research_state.render_research_material(db, paper.id),
            f"# Your task\nExtract what this material tells us about section "
            f"{definition.number}. {definition.title}. Reuse existing labels where the "
            "item is the same. Cite research input IDs in source_input_ids.",
        ]
    )


async def extract_section(
    db: Session, paper: PaperProject, section_key: str
) -> tuple[ExtractionResult, dict]:
    result, _ = await client.run_structured(
        db,
        operation=f"extract:{section_key}",
        system=section_prompt(section_key, "extract"),
        user=_extraction_user_message(db, paper, section_key),
        schema=ExtractionResult,
        paper_id=paper.id,
        branch_id=paper.branch_id,
        max_tokens=8000,
        temperature=0.1,
    )
    stats = research_state.apply_extraction(db, paper.id, section_key, result)
    return result, stats


# --------------------------------------------------------------------------
# Review
# --------------------------------------------------------------------------

def _review_user_message(db: Session, paper: PaperProject, section_key: str) -> str:
    definition = SECTION_BY_KEY[section_key]
    dependency_note = (
        "This section depends on: "
        + ", ".join(SECTION_BY_KEY[d].title for d in definition.depends_on)
        if definition.depends_on
        else "This section has no upstream dependencies."
    )
    return "\n\n".join(
        [
            research_state.paper_context_header(paper),
            "# Research inputs available\n" + research_state.render_input_index(db, paper.id),
            "# Section under review\n"
            + research_state.render_section_state(db, paper.id, section_key),
            f"# Full Research State for context\n({dependency_note})\n\n"
            + research_state.render_full_state(db, paper.id),
            "# Research material (verbatim, for checking evidence)\n"
            + research_state.render_research_material(db, paper.id, char_budget=80_000),
            f"# Your task\nReview section {definition.number}. {definition.title} against "
            "its scientific criteria. Assess what is actually present, not an idealised "
            "version. Ground every issue in the supplied material.",
        ]
    )


def _sync_issues(
    db: Session,
    paper_id: int,
    section_key: str | None,
    origin: str,
    issues: list,
) -> list[Issue]:
    """Replace the previous issues from this origin/section with fresh ones.

    Dismissed issues stay dismissed so a re-check does not resurrect noise the
    researcher has already judged.
    """
    query = select(Issue).where(
        Issue.paper_id == paper_id,
        Issue.origin == origin,
        Issue.status == "open",
    )
    query = (
        query.where(Issue.section_key == section_key)
        if section_key is not None
        else query.where(Issue.section_key.is_(None))
    )
    dismissed_texts = {
        row.issue.strip().lower()
        for row in db.scalars(
            select(Issue).where(Issue.paper_id == paper_id, Issue.status == "dismissed")
        )
    }
    for stale in db.scalars(query):
        db.delete(stale)
    db.flush()

    created: list[Issue] = []
    for entry in issues:
        if entry.issue.strip().lower() in dismissed_texts:
            continue
        row = Issue(
            paper_id=paper_id,
            section_key=section_key,
            origin=origin,
            severity=entry.severity,
            issue=entry.issue,
            why_it_matters=entry.why_it_matters,
            evidence=entry.evidence,
            recommended_action=entry.recommended_action,
            affected_sections=_normalize_sections(entry.affected_sections),
        )
        db.add(row)
        created.append(row)
    db.flush()
    return created


def _normalize_sections(values: list[str] | None) -> list[str]:
    """Resolve model-supplied section names, dropping anything unrecognisable."""
    resolved: list[str] = []
    for value in values or []:
        key = normalize_section_key(value)
        if key and key not in resolved:
            resolved.append(key)
    return [k for k in SECTION_KEYS if k in resolved]


def _reconcile_status(reported: str, issues: list) -> str:
    """A section with an open blocker or major issue is never READY."""
    severities = {i.severity for i in issues}
    if severities & BLOCKING_SEVERITIES and reported == SectionStatus.READY.value:
        return SectionStatus.NEEDS_ATTENTION.value
    return reported


async def review_section(
    db: Session, paper: PaperProject, section_key: str
) -> ReviewResult:
    result, _ = await client.run_structured(
        db,
        operation=f"review:{section_key}",
        system=section_prompt(section_key, "review"),
        user=_review_user_message(db, paper, section_key),
        schema=ReviewResult,
        paper_id=paper.id,
        branch_id=paper.branch_id,
        max_tokens=8000,
        temperature=0.1,
    )

    _sync_issues(db, paper.id, section_key, "section_review", result.issues)

    state = research_state.get_section(db, paper.id, section_key)
    previous_status = state.status
    state.status = _reconcile_status(result.status, result.issues)
    state.summary = result.summary or state.summary
    state.checks = [c.model_dump() for c in result.checks]
    state.missing_information = [m.model_dump() for m in result.missing_information]
    state.last_reviewed_at = utcnow()
    state.needs_recheck = False
    state.recheck_reason = ""
    db.commit()

    if previous_status != state.status:
        research_state.mark_dependents_stale(
            db,
            paper.id,
            section_key,
            f"{SECTION_BY_KEY[section_key].title} changed to "
            f"{state.status.replace('_', ' ')} after review.",
        )
    return result


# --------------------------------------------------------------------------
# Full analysis pass
# --------------------------------------------------------------------------

async def analyze_paper(
    db: Session,
    paper: PaperProject,
    sections: list[str] | None = None,
    run_review: bool = True,
) -> dict:
    """Extract every section, then review the ones with actual content.

    Reviewing empty sections wastes tokens and produces no information: the
    checklist already communicates emptiness.
    """
    targets = sections or list(SECTION_KEYS)
    research_state.ensure_sections(db, paper.id)

    # Fail fast on configuration problems rather than reporting eleven
    # identical per-section errors.
    client.build_provider(db)

    extracted: dict[str, dict] = {}
    reviewed: list[str] = []
    errors: dict[str, str] = {}

    for key in targets:
        try:
            result, stats = await extract_section(db, paper, key)
            extracted[key] = stats
        except Exception as exc:  # noqa: BLE001 - one section must not kill the run
            logger.exception("Extraction failed for section %s", key)
            errors[key] = str(exc)[:500]
            continue

        if run_review and result.coverage != "none":
            try:
                await review_section(db, paper, key)
                reviewed.append(key)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Review failed for section %s", key)
                errors[f"review:{key}"] = str(exc)[:500]

    # Mark the inputs as having been taken into account.
    unanalyzed = db.scalars(
        select(ResearchInput).where(
            ResearchInput.paper_id == paper.id, ResearchInput.analyzed_at.is_(None)
        )
    )
    for research_input in unanalyzed:
        research_input.analyzed_at = utcnow()
    db.commit()

    return {"extracted": extracted, "reviewed": reviewed, "errors": errors}


# --------------------------------------------------------------------------
# Challenge My Research
# --------------------------------------------------------------------------

async def challenge_research(db: Session, paper: PaperProject) -> ChallengeResult:
    user_message = "\n\n".join(
        [
            research_state.paper_context_header(paper),
            "# Research inputs available\n" + research_state.render_input_index(db, paper.id),
            "# Complete Research State\n" + research_state.render_full_state(db, paper.id),
            "# Research material (verbatim)\n"
            + research_state.render_research_material(db, paper.id, char_budget=100_000),
            "# Your task\nPerform the cross-section scientific review. Report the issues "
            "that most threaten the scientific conclusions first.",
        ]
    )
    result, _ = await client.run_structured(
        db,
        operation="challenge",
        system=global_prompt("challenge_research"),
        user=user_message,
        schema=ChallengeResult,
        paper_id=paper.id,
        branch_id=paper.branch_id,
        max_tokens=12000,
        temperature=0.15,
    )

    _sync_issues(db, paper.id, None, "challenge", result.issues)

    # A cross-section blocker invalidates the READY status of the sections it hits.
    for entry in result.issues:
        if entry.severity not in BLOCKING_SEVERITIES:
            continue
        for key in _normalize_sections(entry.affected_sections):
            state = research_state.get_section(db, paper.id, key)
            if state.status == SectionStatus.READY.value:
                state.status = SectionStatus.NEEDS_ATTENTION.value
                state.needs_recheck = True
                state.recheck_reason = f"Challenge raised a {entry.severity}: {entry.issue[:200]}"
    db.commit()
    return result
