"""Research readiness and the Compile Manuscript gate.

Readiness is deliberately expressed as counts and states -- never as a
fabricated score like "82/100", which would imply a precision that does not
exist.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Issue, SectionState
from ..sections import (
    REQUIRED_SECTION_KEYS,
    SECTION_BY_KEY,
    SECTION_KEYS,
    SectionStatus,
    Severity,
)
from .research_state import active_items, ensure_sections


def section_overview(db: Session, paper_id: int) -> list[dict]:
    ensure_sections(db, paper_id)
    states = {
        s.key: s
        for s in db.scalars(select(SectionState).where(SectionState.paper_id == paper_id))
    }
    issues = list(db.scalars(select(Issue).where(Issue.paper_id == paper_id, Issue.status == "open")))
    items = active_items(db, paper_id)

    overview: list[dict] = []
    for key in SECTION_KEYS:
        definition = SECTION_BY_KEY[key]
        state = states[key]
        section_issues = [
            i for i in issues if i.section_key == key or key in (i.affected_sections or [])
        ]
        overview.append(
            {
                "key": key,
                "number": definition.number,
                "title": definition.title,
                "purpose": definition.purpose,
                "status": state.status,
                "summary": state.summary,
                "needs_recheck": state.needs_recheck,
                "recheck_reason": state.recheck_reason,
                "item_count": sum(1 for i in items if i.section_key == key),
                "issue_counts": {
                    severity.value: sum(1 for i in section_issues if i.severity == severity.value)
                    for severity in Severity
                },
                "missing_count": len(state.missing_information or []),
                "depends_on": list(definition.depends_on),
                "last_extracted_at": state.last_extracted_at,
                "last_reviewed_at": state.last_reviewed_at,
            }
        )
    return overview


def compile_gate(db: Session, paper_id: int) -> dict:
    """Compile Manuscript stays locked until the research can defend itself."""
    overview = section_overview(db, paper_id)
    by_key = {s["key"]: s for s in overview}

    not_ready = [
        by_key[k]["title"]
        for k in REQUIRED_SECTION_KEYS
        if by_key[k]["status"] != SectionStatus.READY.value
    ]
    blockers = list(
        db.scalars(
            select(Issue).where(
                Issue.paper_id == paper_id,
                Issue.status == "open",
                Issue.severity == Severity.BLOCKER.value,
            )
        )
    )

    reasons: list[str] = []
    if not_ready:
        listed = ", ".join(not_ready)
        reasons.append(
            f"{len(not_ready)} required section(s) are not READY: {listed}."
        )
    if blockers:
        reasons.append(
            f"{len(blockers)} unresolved BLOCKER issue(s) must be resolved or dismissed."
        )

    ready_count = sum(
        1 for k in REQUIRED_SECTION_KEYS if by_key[k]["status"] == SectionStatus.READY.value
    )
    return {
        "can_compile": not reasons,
        "reasons": reasons,
        "ready_sections": ready_count,
        "required_sections": len(REQUIRED_SECTION_KEYS),
        "open_blockers": len(blockers),
    }


def readiness(db: Session, paper_id: int) -> dict:
    overview = section_overview(db, paper_id)
    gate = compile_gate(db, paper_id)
    counts = {status.value: 0 for status in SectionStatus}
    for section in overview:
        counts[section["status"]] += 1
    return {"sections": overview, "gate": gate, "status_counts": counts}
