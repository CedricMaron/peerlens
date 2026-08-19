"""The Research Checklist: readiness, section detail, corrections, review, challenge."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Issue, PaperProject, Relationship, ResearchInput, ResearchItem, utcnow
from ..schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ChallengeOut,
    IssueOutSchema,
    IssueStatusUpdate,
    ItemCreate,
    ItemUpdate,
    ReadinessOut,
    RelationshipOut,
    ResearchInputListItem,
    ResearchItemOut,
    SectionDetailOut,
)
from ..sections import (
    SECTION_BY_KEY,
    SECTION_ITEM_TYPES,
    SECTION_KEYS,
    SEVERITY_ORDER,
    Confirmation,
    Provenance,
    Severity,
)
from ..services import analysis, readiness, research_state
from ..services import usage as usage_service
from .deps import get_paper

router = APIRouter(tags=["checklist"])


def _severity_rank(severity: str) -> int:
    try:
        return SEVERITY_ORDER[Severity(severity)]
    except ValueError:
        return 99


@router.get("/papers/{paper_id}/readiness", response_model=ReadinessOut)
def get_readiness(paper: PaperProject = Depends(get_paper), db: Session = Depends(get_db)):
    return readiness.readiness(db, paper.id)


@router.get("/papers/{paper_id}/sections/{section_key}", response_model=SectionDetailOut)
def get_section_detail(
    section_key: str,
    paper: PaperProject = Depends(get_paper),
    db: Session = Depends(get_db),
):
    if section_key not in SECTION_BY_KEY:
        raise HTTPException(status_code=404, detail=f"Unknown section '{section_key}'")
    definition = SECTION_BY_KEY[section_key]
    state = research_state.get_section(db, paper.id, section_key)
    items = research_state.active_items(db, paper.id, section_key)

    issues = [
        i
        for i in db.scalars(
            select(Issue).where(Issue.paper_id == paper.id, Issue.status == "open")
        )
        if i.section_key == section_key or section_key in (i.affected_sections or [])
    ]
    issues.sort(key=lambda i: (_severity_rank(i.severity), i.id))

    # Relationships touching this section, rendered with labels for readability.
    all_items = {i.id: i for i in research_state.active_items(db, paper.id)}
    section_item_ids = {i.id for i in items}
    relationships: list[RelationshipOut] = []
    for relation in db.scalars(select(Relationship).where(Relationship.paper_id == paper.id)):
        source = all_items.get(relation.source_item_id)
        target = all_items.get(relation.target_item_id)
        if source is None or target is None:
            continue
        if source.id not in section_item_ids and target.id not in section_item_ids:
            continue
        relationships.append(
            RelationshipOut(
                id=relation.id,
                rel_type=relation.rel_type,
                rationale=relation.rationale,
                source_label=source.label,
                target_label=target.label,
                source_section=source.section_key,
                target_section=target.section_key,
            )
        )

    # The research inputs this section's understanding actually came from.
    cited_ids = {sid for item in items for sid in (item.source_input_ids or [])}
    sources: list[ResearchInputListItem] = []
    if cited_ids:
        for row in db.scalars(
            select(ResearchInput).where(ResearchInput.id.in_(cited_ids)).order_by(ResearchInput.id)
        ):
            payload = ResearchInputListItem.model_validate(row)
            payload.char_count = len(row.content or "")
            preview = (row.content or "").strip().replace("\n", " ")
            payload.preview = preview[:220] + ("…" if len(preview) > 220 else "")
            sources.append(payload)

    return SectionDetailOut(
        key=section_key,
        number=definition.number,
        title=definition.title,
        purpose=definition.purpose,
        status=state.status,
        summary=state.summary,
        needs_recheck=state.needs_recheck,
        recheck_reason=state.recheck_reason,
        checks=state.checks or [],
        missing_information=state.missing_information or [],
        items=[ResearchItemOut.model_validate(i) for i in items],
        issues=[IssueOutSchema.model_validate(i) for i in issues],
        relationships=relationships,
        sources=sources,
        depends_on=list(definition.depends_on),
        last_extracted_at=state.last_extracted_at,
        last_reviewed_at=state.last_reviewed_at,
    )


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------

@router.post("/papers/{paper_id}/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest | None = None,
    paper: PaperProject = Depends(get_paper),
    db: Session = Depends(get_db),
):
    request = payload or AnalyzeRequest()
    if request.sections:
        unknown = [s for s in request.sections if s not in SECTION_BY_KEY]
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown sections: {unknown}")
    # A provider failure propagates: the application-level handler turns it
    # into a 400 carrying a normalized error code.
    outcome = await analysis.analyze_paper(
        db, paper, sections=request.sections, run_review=request.run_review
    )
    return AnalyzeResponse(
        **outcome,
        readiness=readiness.readiness(db, paper.id),
        meta=usage_service.last_event_meta(db, paper.id),
    )


@router.post("/papers/{paper_id}/sections/{section_key}/extract")
async def extract_one(
    section_key: str,
    paper: PaperProject = Depends(get_paper),
    db: Session = Depends(get_db),
):
    if section_key not in SECTION_BY_KEY:
        raise HTTPException(status_code=404, detail=f"Unknown section '{section_key}'")
    _, stats = await analysis.extract_section(db, paper, section_key)
    return {"section": section_key, "stats": stats}


@router.post("/papers/{paper_id}/sections/{section_key}/review", response_model=SectionDetailOut)
async def review_one(
    section_key: str,
    paper: PaperProject = Depends(get_paper),
    db: Session = Depends(get_db),
):
    """Re-check a single section against its scientific criteria."""
    if section_key not in SECTION_BY_KEY:
        raise HTTPException(status_code=404, detail=f"Unknown section '{section_key}'")
    await analysis.review_section(db, paper, section_key)
    return get_section_detail(section_key, paper, db)


@router.post("/papers/{paper_id}/sections/{section_key}/recheck", response_model=SectionDetailOut)
async def recheck_one(
    section_key: str,
    paper: PaperProject = Depends(get_paper),
    db: Session = Depends(get_db),
):
    """Re-extract from the material, then review. Used after adding information."""
    if section_key not in SECTION_BY_KEY:
        raise HTTPException(status_code=404, detail=f"Unknown section '{section_key}'")
    await analysis.extract_section(db, paper, section_key)
    await analysis.review_section(db, paper, section_key)
    return get_section_detail(section_key, paper, db)


@router.post("/papers/{paper_id}/challenge", response_model=ChallengeOut)
async def challenge(paper: PaperProject = Depends(get_paper), db: Session = Depends(get_db)):
    result = await analysis.challenge_research(db, paper)
    issues = list(
        db.scalars(
            select(Issue).where(
                Issue.paper_id == paper.id, Issue.origin == "challenge", Issue.status == "open"
            )
        )
    )
    issues.sort(key=lambda i: (_severity_rank(i.severity), i.id))
    return ChallengeOut(
        overall_assessment=result.overall_assessment,
        cross_section_observations=result.cross_section_observations,
        issues=[IssueOutSchema.model_validate(i) for i in issues],
        meta=usage_service.last_event_meta(db, paper.id, "challenge"),
    )


@router.get("/papers/{paper_id}/issues", response_model=list[IssueOutSchema])
def list_issues(
    status: str = "open",
    paper: PaperProject = Depends(get_paper),
    db: Session = Depends(get_db),
):
    query = select(Issue).where(Issue.paper_id == paper.id)
    if status != "all":
        query = query.where(Issue.status == status)
    issues = list(db.scalars(query))
    issues.sort(key=lambda i: (_severity_rank(i.severity), i.id))
    return [IssueOutSchema.model_validate(i) for i in issues]


@router.patch("/issues/{issue_id}", response_model=IssueOutSchema)
def update_issue(issue_id: int, payload: IssueStatusUpdate, db: Session = Depends(get_db)):
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    issue.status = payload.status
    db.commit()
    return IssueOutSchema.model_validate(issue)


# --------------------------------------------------------------------------
# Human control over the model's understanding
# --------------------------------------------------------------------------

def _touch_dependents(db: Session, paper_id: int, section_key: str, reason: str) -> None:
    research_state.mark_dependents_stale(db, paper_id, section_key, reason)


@router.post("/papers/{paper_id}/items", response_model=ResearchItemOut, status_code=201)
def create_item(
    payload: ItemCreate,
    paper: PaperProject = Depends(get_paper),
    db: Session = Depends(get_db),
):
    """A researcher-authored item. Provenance is PROVIDED, never AI-derived."""
    if payload.section_key not in SECTION_BY_KEY:
        raise HTTPException(status_code=404, detail=f"Unknown section '{payload.section_key}'")
    existing = research_state.active_items(db, paper.id, payload.section_key)
    label = payload.label.strip() or f"{payload.section_key[:3].upper()}{len(existing) + 1}"
    item = ResearchItem(
        paper_id=paper.id,
        section_key=payload.section_key,
        item_type=SECTION_ITEM_TYPES[payload.section_key],
        label=label,
        statement=payload.statement,
        details=payload.details,
        provenance=Provenance.PROVIDED.value,
        confirmation=Confirmation.CONFIRMED.value,
        order_index=len(existing),
    )
    db.add(item)
    db.commit()
    _touch_dependents(
        db, paper.id, payload.section_key, f"Researcher added {label} to {payload.section_key}."
    )
    return ResearchItemOut.model_validate(item)


@router.patch("/items/{item_id}", response_model=ResearchItemOut)
def edit_item(item_id: int, payload: ItemUpdate, db: Session = Depends(get_db)):
    """Correct what the model understood. Marks the item as researcher-edited."""
    item = db.get(ResearchItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Research item not found")
    if payload.statement is not None:
        item.statement = payload.statement
    if payload.details is not None:
        item.details = payload.details
    if payload.label is not None and payload.label.strip():
        item.label = payload.label.strip()
    item.confirmation = Confirmation.EDITED.value
    item.updated_at = utcnow()
    db.commit()
    _touch_dependents(
        db, item.paper_id, item.section_key, f"Researcher edited {item.label}."
    )
    return ResearchItemOut.model_validate(item)


@router.post("/items/{item_id}/confirm", response_model=ResearchItemOut)
def confirm_item(item_id: int, db: Session = Depends(get_db)):
    """Promote AI understanding to researcher-confirmed. Never done silently."""
    item = db.get(ResearchItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Research item not found")
    item.confirmation = Confirmation.CONFIRMED.value
    item.updated_at = utcnow()
    db.commit()
    return ResearchItemOut.model_validate(item)


@router.post("/items/{item_id}/reject", response_model=ResearchItemOut)
def reject_item(item_id: int, db: Session = Depends(get_db)):
    """Reject an extraction. It will not be reintroduced by later analysis."""
    item = db.get(ResearchItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Research item not found")
    item.confirmation = Confirmation.REJECTED.value
    item.active = False
    item.updated_at = utcnow()
    db.commit()
    _touch_dependents(
        db, item.paper_id, item.section_key, f"Researcher rejected {item.label}."
    )
    return ResearchItemOut.model_validate(item)


@router.get("/papers/{paper_id}/items", response_model=list[ResearchItemOut])
def list_items(paper: PaperProject = Depends(get_paper), db: Session = Depends(get_db)):
    return [
        ResearchItemOut.model_validate(i) for i in research_state.active_items(db, paper.id)
    ]


@router.get("/sections", response_model=list[dict])
def list_section_definitions():
    """Static checklist definition, used by the frontend for ordering and labels."""
    return [
        {
            "key": key,
            "number": SECTION_BY_KEY[key].number,
            "title": SECTION_BY_KEY[key].title,
            "purpose": SECTION_BY_KEY[key].purpose,
            "depends_on": list(SECTION_BY_KEY[key].depends_on),
        }
        for key in SECTION_KEYS
    ]
