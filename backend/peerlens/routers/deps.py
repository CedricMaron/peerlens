"""Shared router dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Path
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PaperProject, ResearchBranch


def get_branch(
    branch_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> ResearchBranch:
    branch = db.get(ResearchBranch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="Research branch not found")
    return branch


def get_paper(
    paper_id: int = Path(..., ge=1), db: Session = Depends(get_db)
) -> PaperProject:
    paper = db.get(PaperProject, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper project not found")
    return paper
