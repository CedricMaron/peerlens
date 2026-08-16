"""The Research State: building it, rendering it, and keeping it honest.

Two rules govern this module:

1. A researcher's confirmation or correction is never overwritten by a later
   AI extraction.
2. Everything rendered into a prompt carries its provenance and its source, so
   the model can tell what is established from what is inferred.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai_schemas import ExtractionResult
from ..models import PaperProject, Relationship, ResearchInput, ResearchItem, SectionState, utcnow
from ..sections import (
    SECTION_BY_KEY,
    SECTION_ITEM_TYPES,
    SECTION_KEYS,
    Confirmation,
    Provenance,
    SectionStatus,
    dependents_of,
)

COVERAGE_TO_STATUS = {
    "none": SectionStatus.MISSING,
    "partial": SectionStatus.INCOMPLETE,
    "substantial": SectionStatus.INCOMPLETE,
}


# --------------------------------------------------------------------------
# Section bookkeeping
# --------------------------------------------------------------------------

def ensure_sections(db: Session, paper_id: int) -> list[SectionState]:
    """Create the eleven checklist rows for a paper if they do not exist yet."""
    existing = {
        s.key: s
        for s in db.scalars(select(SectionState).where(SectionState.paper_id == paper_id))
    }
    created = False
    for key in SECTION_KEYS:
        if key not in existing:
            state = SectionState(paper_id=paper_id, key=key, status=SectionStatus.MISSING.value)
            db.add(state)
            existing[key] = state
            created = True
    if created:
        db.commit()
    return [existing[key] for key in SECTION_KEYS]


def get_section(db: Session, paper_id: int, key: str) -> SectionState:
    ensure_sections(db, paper_id)
    state = db.scalar(
        select(SectionState).where(
            SectionState.paper_id == paper_id, SectionState.key == key
        )
    )
    if state is None:  # pragma: no cover - ensure_sections guarantees existence
        raise KeyError(f"Unknown section {key}")
    return state


def active_items(db: Session, paper_id: int, section_key: str | None = None) -> list[ResearchItem]:
    query = select(ResearchItem).where(
        ResearchItem.paper_id == paper_id,
        ResearchItem.active.is_(True),
        ResearchItem.confirmation != Confirmation.REJECTED.value,
    )
    if section_key:
        query = query.where(ResearchItem.section_key == section_key)
    items = list(db.scalars(query))
    items.sort(key=lambda i: (SECTION_KEYS.index(i.section_key), i.order_index, i.id))
    return items


def mark_dependents_stale(db: Session, paper_id: int, changed_section: str, reason: str) -> list[str]:
    """Research evolves: propagate change forward through the dependency graph.

    A READY section legitimately returns to NEEDS ATTENTION when the evidence
    beneath it changes.
    """
    affected: list[str] = []
    for key in dependents_of(changed_section):
        state = get_section(db, paper_id, key)
        if state.status == SectionStatus.MISSING.value and not state.summary:
            continue  # nothing to invalidate yet
        state.needs_recheck = True
        state.recheck_reason = reason
        if state.status == SectionStatus.READY.value:
            state.status = SectionStatus.NEEDS_ATTENTION.value
        affected.append(key)
    if affected:
        db.commit()
    return affected


# --------------------------------------------------------------------------
# Applying an extraction
# --------------------------------------------------------------------------

def apply_extraction(
    db: Session, paper_id: int, section_key: str, result: ExtractionResult
) -> dict:
    """Merge an extraction into the Research State.

    Items the researcher has confirmed or edited keep their content. Items the
    researcher rejected are not resurrected. Unconfirmed items that the new
    extraction no longer supports are deactivated rather than deleted.
    """
    item_type = SECTION_ITEM_TYPES[section_key]
    existing = list(
        db.scalars(
            select(ResearchItem).where(
                ResearchItem.paper_id == paper_id,
                ResearchItem.section_key == section_key,
            )
        )
    )
    by_label = {i.label.strip().lower(): i for i in existing if i.label}

    seen_ids: set[int] = set()
    added, updated, protected = 0, 0, 0

    for order, extracted in enumerate(result.items):
        label = (extracted.label or f"{section_key[:1].upper()}{order + 1}").strip()
        current = by_label.get(label.lower())

        if current is not None and current.confirmation == Confirmation.REJECTED.value:
            continue  # the researcher rejected this; do not bring it back

        if current is None:
            current = ResearchItem(
                paper_id=paper_id,
                section_key=section_key,
                item_type=item_type,
                label=label,
            )
            db.add(current)
            added += 1
        elif current.confirmation in (Confirmation.CONFIRMED.value, Confirmation.EDITED.value):
            # Researcher-owned content: only widen the source list, never rewrite.
            merged = sorted(set(current.source_input_ids or []) | set(extracted.source_input_ids))
            current.source_input_ids = merged
            current.active = True
            protected += 1
            db.flush()
            seen_ids.add(current.id)
            continue
        else:
            updated += 1

        current.statement = extracted.statement
        current.details = extracted.details
        current.provenance = extracted.provenance
        current.source_input_ids = extracted.source_input_ids
        current.order_index = order
        current.active = True
        db.flush()
        seen_ids.add(current.id)

    deactivated = 0
    for item in existing:
        if item.id in seen_ids or not item.active:
            continue
        if item.confirmation in (Confirmation.CONFIRMED.value, Confirmation.EDITED.value):
            continue  # researcher-owned items survive re-extraction
        item.active = False
        deactivated += 1

    db.flush()
    _rebuild_relationships(db, paper_id, section_key, result)

    state = get_section(db, paper_id, section_key)
    state.summary = result.section_summary
    state.last_extracted_at = utcnow()
    if state.status in (SectionStatus.MISSING.value, SectionStatus.INCOMPLETE.value):
        state.status = COVERAGE_TO_STATUS.get(result.coverage, SectionStatus.INCOMPLETE).value
    if result.coverage != "none" and state.status == SectionStatus.MISSING.value:
        state.status = SectionStatus.INCOMPLETE.value
    db.commit()

    return {
        "added": added,
        "updated": updated,
        "protected": protected,
        "deactivated": deactivated,
        "coverage": result.coverage,
    }


def _rebuild_relationships(
    db: Session, paper_id: int, section_key: str, result: ExtractionResult
) -> None:
    """Replace AI-derived relationships originating in this section."""
    section_item_ids = [
        i.id
        for i in db.scalars(
            select(ResearchItem).where(
                ResearchItem.paper_id == paper_id, ResearchItem.section_key == section_key
            )
        )
    ]
    if section_item_ids:
        stale = db.scalars(
            select(Relationship).where(
                Relationship.paper_id == paper_id,
                Relationship.source_item_id.in_(section_item_ids),
                Relationship.provenance != Provenance.PROVIDED.value,
            )
        )
        for row in stale:
            db.delete(row)
        db.flush()

    label_index = {
        i.label.strip().lower(): i
        for i in active_items(db, paper_id)
        if i.label
    }
    for extracted in result.items:
        source = label_index.get((extracted.label or "").strip().lower())
        if source is None:
            continue
        for relation in extracted.relations:
            target = label_index.get(relation.target_label.strip().lower())
            if target is None or target.id == source.id:
                continue  # never invent a relationship to a non-existent item
            db.add(
                Relationship(
                    paper_id=paper_id,
                    source_item_id=source.id,
                    target_item_id=target.id,
                    rel_type=relation.rel_type,
                    rationale=relation.rationale,
                    provenance=Provenance.INFERRED.value,
                )
            )
    db.flush()


# --------------------------------------------------------------------------
# Rendering for prompts
# --------------------------------------------------------------------------

def render_research_material(
    db: Session, paper_id: int, char_budget: int = 120_000
) -> str:
    """The researcher's raw material, with stable IDs the model must cite."""
    inputs = list(
        db.scalars(
            select(ResearchInput)
            .where(ResearchInput.paper_id == paper_id)
            .order_by(ResearchInput.id)
        )
    )
    if not inputs:
        return "(No research material has been added to this paper project yet.)"

    per_input = max(2_000, char_budget // max(len(inputs), 1))
    blocks: list[str] = []
    for item in inputs:
        content = item.content or ""
        clipped = ""
        if len(content) > per_input:
            content = content[:per_input]
            clipped = f"\n[... truncated, {len(item.content) - per_input:,} more characters ...]"
        header = f"### RESEARCH INPUT {item.id} — {item.label or item.original_filename or 'untitled'}"
        meta = [f"added {item.created_at:%Y-%m-%d}"]
        if item.original_filename:
            meta.append(f"file: {item.original_filename}")
        if item.extraction_note:
            meta.append(item.extraction_note)
        blocks.append(f"{header}\n({'; '.join(meta)})\n\n{content}{clipped}")
    return "\n\n".join(blocks)


def _format_item(item: ResearchItem) -> str:
    tag = item.provenance
    if item.confirmation == Confirmation.CONFIRMED.value:
        tag += ", confirmed by researcher"
    elif item.confirmation == Confirmation.EDITED.value:
        tag += ", edited by researcher"
    sources = (
        f" sources: {', '.join(f'#{s}' for s in item.source_input_ids)}"
        if item.source_input_ids
        else " sources: none"
    )
    lines = [f"- [{item.label}] ({tag};{sources}) {item.statement}"]
    for key, value in (item.details or {}).items():
        if value:
            lines.append(f"    {key}: {value}")
    return "\n".join(lines)


def render_section_state(db: Session, paper_id: int, section_key: str) -> str:
    """Current understanding of one section, for its review prompt."""
    state = get_section(db, paper_id, section_key)
    items = active_items(db, paper_id, section_key)
    definition = SECTION_BY_KEY[section_key]

    parts = [f"## Current understanding — {definition.title}"]
    parts.append(state.summary or "(no summary extracted yet)")
    if items:
        parts.append("\n### Items")
        parts.append("\n".join(_format_item(i) for i in items))
    else:
        parts.append("\n### Items\n(none extracted)")
    return "\n".join(parts)


def render_full_state(
    db: Session, paper_id: int, exclude: str | None = None, include_relationships: bool = True
) -> str:
    """The whole Research State, used by reviews, Challenge and compilation."""
    parts: list[str] = []
    for key in SECTION_KEYS:
        if key == exclude:
            continue
        definition = SECTION_BY_KEY[key]
        state = get_section(db, paper_id, key)
        items = active_items(db, paper_id, key)
        block = [f"## {definition.number}. {definition.title} [status: {state.status}]"]
        if state.summary:
            block.append(state.summary)
        if items:
            block.append("\n".join(_format_item(i) for i in items))
        elif not state.summary:
            block.append("(nothing extracted for this section yet)")
        parts.append("\n".join(block))

    if include_relationships:
        relations = list(
            db.scalars(select(Relationship).where(Relationship.paper_id == paper_id))
        )
        if relations:
            index = {i.id: i for i in active_items(db, paper_id)}
            lines = []
            for relation in relations:
                source = index.get(relation.source_item_id)
                target = index.get(relation.target_item_id)
                if source and target:
                    suffix = f" — {relation.rationale}" if relation.rationale else ""
                    lines.append(
                        f"- {source.label} --{relation.rel_type}--> {target.label}{suffix}"
                    )
            if lines:
                parts.append("## Scientific relationships\n" + "\n".join(lines))

    return "\n\n".join(parts)


def render_input_index(db: Session, paper_id: int) -> str:
    """A compact table of input IDs so the model can cite provenance."""
    inputs = list(
        db.scalars(
            select(ResearchInput)
            .where(ResearchInput.paper_id == paper_id)
            .order_by(ResearchInput.id)
        )
    )
    if not inputs:
        return "(no research inputs)"
    return "\n".join(
        f"- #{i.id}: {i.label or i.original_filename or 'untitled'} "
        f"({i.kind}, added {i.created_at:%Y-%m-%d})"
        for i in inputs
    )


def paper_context_header(paper: PaperProject) -> str:
    header = f"# Paper project: {paper.title}"
    if paper.branch is not None:
        header += f"\nResearch branch: {paper.branch.name}"
        if paper.branch.description:
            header += f" — {paper.branch.description}"
    if paper.notes:
        header += f"\nResearcher's note about this paper: {paper.notes}"
    return header
