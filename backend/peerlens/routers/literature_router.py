"""Literature search and library management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..llm.base import LLMError
from ..models import LiteratureItem, PaperLiterature, PaperProject, ResearchBranch
from ..schemas import (
    LiteratureAnalysisOut,
    LiteratureCreate,
    LiteratureOut,
    LiteratureSearchResult,
    LiteratureUpdate,
)
from ..services import literature
from .deps import get_branch, get_paper

router = APIRouter(tags=["literature"])


def _to_out(db: Session, item: LiteratureItem) -> LiteratureOut:
    payload = LiteratureOut.model_validate(item)
    payload.attached_paper_ids = [
        row.paper_id
        for row in db.scalars(
            select(PaperLiterature).where(PaperLiterature.literature_id == item.id)
        )
    ]
    return payload


@router.get("/literature/search", response_model=list[LiteratureSearchResult])
async def search(
    q: str = Query(..., min_length=2),
    branch_id: int | None = None,
    limit: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Search OpenAlex. Results are what the API returned, nothing more."""
    try:
        results = await literature.search_openalex(q, limit)
    except literature.LiteratureSearchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    known_dois: set[str] = set()
    known_ids: set[str] = set()
    if branch_id is not None:
        for item in db.scalars(
            select(LiteratureItem).where(LiteratureItem.branch_id == branch_id)
        ):
            if item.doi:
                known_dois.add(item.doi.lower())
            if item.external_id:
                known_ids.add(item.external_id)

    payload: list[LiteratureSearchResult] = []
    for result in results:
        entry = LiteratureSearchResult(**result)
        entry.already_in_library = bool(
            (entry.doi and entry.doi.lower() in known_dois)
            or (entry.external_id and entry.external_id in known_ids)
        )
        payload.append(entry)
    return payload


@router.get("/literature/doi", response_model=LiteratureSearchResult)
async def lookup_doi(doi: str = Query(..., min_length=5)):
    try:
        result = await literature.fetch_by_doi(doi)
    except literature.LiteratureSearchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"No work found for DOI '{doi}'.")
    return LiteratureSearchResult(**result)


@router.get("/branches/{branch_id}/literature", response_model=list[LiteratureOut])
def list_literature(
    branch: ResearchBranch = Depends(get_branch), db: Session = Depends(get_db)
):
    items = db.scalars(
        select(LiteratureItem)
        .where(LiteratureItem.branch_id == branch.id)
        .order_by(LiteratureItem.created_at.desc())
    )
    return [_to_out(db, item) for item in items]


@router.post("/branches/{branch_id}/literature", response_model=LiteratureOut, status_code=201)
def add_literature(
    payload: LiteratureCreate,
    branch: ResearchBranch = Depends(get_branch),
    db: Session = Depends(get_db),
):
    existing = None
    if payload.doi:
        existing = db.scalar(
            select(LiteratureItem).where(
                LiteratureItem.branch_id == branch.id,
                LiteratureItem.doi == payload.doi,
            )
        )
    item = existing or LiteratureItem(branch_id=branch.id)
    for field in (
        "title", "authors", "year", "doi", "abstract", "venue", "url",
        "source", "external_id", "verification_status", "relation_to_research",
        "relation_kind",
    ):
        setattr(item, field, getattr(payload, field))
    if existing is None:
        db.add(item)
    db.commit()

    if payload.paper_id is not None:
        paper = db.get(PaperProject, payload.paper_id)
        if paper is None or paper.branch_id != branch.id:
            raise HTTPException(status_code=400, detail="Paper is not in this branch.")
        literature.attach_to_paper(db, item.id, paper.id)
    return _to_out(db, item)


@router.patch("/literature/{literature_id}", response_model=LiteratureOut)
def update_literature(
    literature_id: int, payload: LiteratureUpdate, db: Session = Depends(get_db)
):
    item = db.get(LiteratureItem, literature_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Reference not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    db.commit()
    return _to_out(db, item)


@router.delete("/literature/{literature_id}", status_code=204)
def delete_literature(literature_id: int, db: Session = Depends(get_db)):
    item = db.get(LiteratureItem, literature_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Reference not found")
    db.delete(item)
    db.commit()


@router.post("/papers/{paper_id}/literature/{literature_id}", status_code=204)
def attach(
    literature_id: int,
    paper: PaperProject = Depends(get_paper),
    db: Session = Depends(get_db),
):
    item = db.get(LiteratureItem, literature_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Reference not found")
    literature.attach_to_paper(db, literature_id, paper.id)


@router.delete("/papers/{paper_id}/literature/{literature_id}", status_code=204)
def detach(
    literature_id: int,
    paper: PaperProject = Depends(get_paper),
    db: Session = Depends(get_db),
):
    link = db.scalar(
        select(PaperLiterature).where(
            PaperLiterature.paper_id == paper.id,
            PaperLiterature.literature_id == literature_id,
        )
    )
    if link is not None:
        db.delete(link)
        db.commit()


@router.get("/papers/{paper_id}/literature", response_model=list[LiteratureOut])
def list_paper_literature(
    paper: PaperProject = Depends(get_paper), db: Session = Depends(get_db)
):
    items = db.scalars(
        select(LiteratureItem)
        .join(PaperLiterature, PaperLiterature.literature_id == LiteratureItem.id)
        .where(PaperLiterature.paper_id == paper.id)
    )
    return [_to_out(db, item) for item in items]


@router.post("/papers/{paper_id}/literature/analyze", response_model=LiteratureAnalysisOut)
async def analyze(paper: PaperProject = Depends(get_paper), db: Session = Depends(get_db)):
    try:
        result = await literature.analyze_literature(db, paper)
    except LLMError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LiteratureAnalysisOut(**result.model_dump())
