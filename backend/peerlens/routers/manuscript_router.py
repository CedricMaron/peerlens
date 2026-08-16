"""Compile Manuscript — locked until the research can defend itself."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..llm.base import LLMError
from ..models import Manuscript, PaperProject
from ..schemas import CompileGate, ManuscriptOut
from ..services import manuscript as manuscript_service
from ..services.readiness import compile_gate
from .deps import get_paper

router = APIRouter(tags=["manuscript"])


@router.get("/papers/{paper_id}/manuscript/gate", response_model=CompileGate)
def gate(paper: PaperProject = Depends(get_paper), db: Session = Depends(get_db)):
    return compile_gate(db, paper.id)


@router.post("/papers/{paper_id}/manuscript", response_model=ManuscriptOut)
async def compile_manuscript(
    paper: PaperProject = Depends(get_paper), db: Session = Depends(get_db)
):
    try:
        result = await manuscript_service.compile_manuscript(db, paper)
    except manuscript_service.ManuscriptLocked as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Compile Manuscript is locked.",
                "reasons": exc.reasons,
            },
        ) from exc
    except LLMError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ManuscriptOut.model_validate(result)


@router.get("/papers/{paper_id}/manuscripts", response_model=list[ManuscriptOut])
def list_manuscripts(paper: PaperProject = Depends(get_paper), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Manuscript)
        .where(Manuscript.paper_id == paper.id)
        .order_by(Manuscript.created_at.desc())
    )
    return [ManuscriptOut.model_validate(row) for row in rows]


@router.get("/manuscripts/{manuscript_id}/markdown")
def download_markdown(manuscript_id: int, db: Session = Depends(get_db)):
    row = db.get(Manuscript, manuscript_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Manuscript not found")
    filename = f"manuscript-{row.paper_id}-{row.created_at:%Y%m%d-%H%M}.md"
    return Response(
        content=row.markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
