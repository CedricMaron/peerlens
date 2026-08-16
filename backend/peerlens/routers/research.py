"""Research branches, paper projects, and the universal research input."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import MAX_UPLOAD_BYTES
from ..db import get_db
from ..models import (
    LiteratureItem,
    PaperProject,
    ResearchBranch,
    ResearchInput,
)
from ..schemas import (
    BranchCreate,
    BranchOut,
    BranchUpdate,
    PaperCreate,
    PaperSummary,
    PaperUpdate,
    ResearchInputCreate,
    ResearchInputListItem,
    ResearchInputOut,
)
from ..services import ingest, research_state
from .deps import get_branch, get_paper

router = APIRouter(tags=["research"])


def _branch_out(db: Session, branch: ResearchBranch) -> BranchOut:
    count = db.scalar(
        select(func.count(LiteratureItem.id)).where(LiteratureItem.branch_id == branch.id)
    )
    payload = BranchOut.model_validate(branch)
    payload.literature_count = count or 0
    return payload


# --------------------------------------------------------------------------
# Branches
# --------------------------------------------------------------------------

@router.get("/branches", response_model=list[BranchOut])
def list_branches(db: Session = Depends(get_db)):
    branches = db.scalars(select(ResearchBranch).order_by(ResearchBranch.created_at.desc()))
    return [_branch_out(db, branch) for branch in branches]


@router.post("/branches", response_model=BranchOut, status_code=201)
def create_branch(payload: BranchCreate, db: Session = Depends(get_db)):
    branch = ResearchBranch(name=payload.name.strip(), description=payload.description)
    db.add(branch)
    db.commit()
    return _branch_out(db, branch)


@router.get("/branches/{branch_id}", response_model=BranchOut)
def read_branch(branch: ResearchBranch = Depends(get_branch), db: Session = Depends(get_db)):
    return _branch_out(db, branch)


@router.patch("/branches/{branch_id}", response_model=BranchOut)
def update_branch(
    payload: BranchUpdate,
    branch: ResearchBranch = Depends(get_branch),
    db: Session = Depends(get_db),
):
    if payload.name is not None:
        branch.name = payload.name.strip()
    if payload.description is not None:
        branch.description = payload.description
    db.commit()
    return _branch_out(db, branch)


@router.delete("/branches/{branch_id}", status_code=204)
def delete_branch(branch: ResearchBranch = Depends(get_branch), db: Session = Depends(get_db)):
    db.delete(branch)
    db.commit()


# --------------------------------------------------------------------------
# Paper projects
# --------------------------------------------------------------------------

@router.post("/branches/{branch_id}/papers", response_model=PaperSummary, status_code=201)
def create_paper(
    payload: PaperCreate,
    branch: ResearchBranch = Depends(get_branch),
    db: Session = Depends(get_db),
):
    paper = PaperProject(branch_id=branch.id, title=payload.title.strip(), notes=payload.notes)
    db.add(paper)
    db.commit()
    research_state.ensure_sections(db, paper.id)
    return PaperSummary.model_validate(paper)


@router.get("/papers/{paper_id}", response_model=PaperSummary)
def read_paper(paper: PaperProject = Depends(get_paper)):
    return PaperSummary.model_validate(paper)


@router.patch("/papers/{paper_id}", response_model=PaperSummary)
def update_paper(
    payload: PaperUpdate,
    paper: PaperProject = Depends(get_paper),
    db: Session = Depends(get_db),
):
    if payload.title is not None:
        paper.title = payload.title.strip()
    if payload.notes is not None:
        paper.notes = payload.notes
    db.commit()
    return PaperSummary.model_validate(paper)


@router.delete("/papers/{paper_id}", status_code=204)
def delete_paper(paper: PaperProject = Depends(get_paper), db: Session = Depends(get_db)):
    db.delete(paper)
    db.commit()


# --------------------------------------------------------------------------
# Research inputs — free-form, never forced into a form
# --------------------------------------------------------------------------

def _list_item(row: ResearchInput) -> ResearchInputListItem:
    payload = ResearchInputListItem.model_validate(row)
    payload.char_count = len(row.content or "")
    preview = (row.content or "").strip().replace("\n", " ")
    payload.preview = preview[:220] + ("…" if len(preview) > 220 else "")
    return payload


@router.get("/papers/{paper_id}/inputs", response_model=list[ResearchInputListItem])
def list_inputs(paper: PaperProject = Depends(get_paper), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ResearchInput)
        .where(ResearchInput.paper_id == paper.id)
        .order_by(ResearchInput.created_at.desc())
    )
    return [_list_item(row) for row in rows]


@router.get("/inputs/{input_id}", response_model=ResearchInputOut)
def read_input(input_id: int, db: Session = Depends(get_db)):
    row = db.get(ResearchInput, input_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Research input not found")
    return ResearchInputOut.model_validate(row)


@router.post("/papers/{paper_id}/inputs", response_model=ResearchInputOut, status_code=201)
def add_text_input(
    payload: ResearchInputCreate,
    paper: PaperProject = Depends(get_paper),
    db: Session = Depends(get_db),
):
    """Save free-form text. This never calls an LLM."""
    row = ResearchInput(
        paper_id=paper.id,
        label=payload.label.strip() or "Research note",
        kind="text",
        content=payload.content,
        byte_size=len(payload.content.encode("utf-8")),
    )
    db.add(row)
    db.commit()
    _invalidate_after_new_input(db, paper.id, row.label)
    return ResearchInputOut.model_validate(row)


@router.post("/papers/{paper_id}/inputs/upload", response_model=list[ResearchInputOut], status_code=201)
async def upload_inputs(
    files: list[UploadFile] = File(...),
    label: str = Form(""),
    paper: PaperProject = Depends(get_paper),
    db: Session = Depends(get_db),
):
    """Upload research files. The original bytes are always preserved on disk."""
    created: list[ResearchInput] = []
    for upload in files:
        filename = upload.filename or "upload"
        if not ingest.is_supported(filename):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type for '{filename}'. Supported: "
                + ", ".join(sorted(ingest.SUPPORTED_EXTENSIONS)),
            )
        data = await upload.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"'{filename}' exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
            )
        stored = ingest.store_upload(data, filename)
        outcome = ingest.extract_text(data, filename)
        row = ResearchInput(
            paper_id=paper.id,
            label=label.strip() or filename,
            kind="file",
            content=outcome.text,
            original_filename=filename,
            stored_path=str(stored),
            content_type=upload.content_type,
            byte_size=len(data),
            extraction_note=outcome.note,
        )
        db.add(row)
        created.append(row)
    db.commit()
    _invalidate_after_new_input(db, paper.id, ", ".join(r.label for r in created))
    return [ResearchInputOut.model_validate(row) for row in created]


@router.delete("/inputs/{input_id}", status_code=204)
def delete_input(input_id: int, db: Session = Depends(get_db)):
    row = db.get(ResearchInput, input_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Research input not found")
    db.delete(row)
    db.commit()


def _invalidate_after_new_input(db: Session, paper_id: int, label: str) -> None:
    """New material can change any section, so every section owes a re-check."""
    reason = f"New research material added ({label[:120]}). Re-analysis needed."
    for state in research_state.ensure_sections(db, paper_id):
        if state.last_extracted_at is not None:
            state.needs_recheck = True
            state.recheck_reason = reason
    db.commit()
