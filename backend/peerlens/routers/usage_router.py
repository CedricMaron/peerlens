"""AI usage tracking endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import UsageEventOut, UsageOverview
from ..services import usage

router = APIRouter(tags=["usage"])


@router.get("/usage", response_model=UsageOverview)
def usage_overview(
    paper_id: int | None = None,
    branch_id: int | None = None,
    since_days: int | None = Query(None, ge=1, le=3650),
    db: Session = Depends(get_db),
):
    scope = {"paper_id": paper_id, "branch_id": branch_id, "since_days": since_days}
    return UsageOverview(
        totals=usage.totals(db, **scope),
        by_operation=usage.breakdown(db, "operation", **scope),
        by_provider=usage.breakdown(db, "provider", **scope),
        by_model=usage.breakdown(db, "model", **scope),
        by_paper=usage.breakdown(db, "paper", **scope),
        by_branch=usage.breakdown(db, "branch", **scope),
        by_location=usage.breakdown(db, "location", **scope),
        recent=[
            UsageEventOut.model_validate(e) for e in usage.recent_events(db, 100, paper_id)
        ],
    )


@router.get("/usage/summary")
def usage_summary(db: Session = Depends(get_db)):
    """Compact figures for the header, e.g. `Tokens 128k · $0.84`."""
    totals = usage.totals(db)
    return {
        "total_tokens": totals["total_tokens"],
        "estimated_cost": totals["estimated_cost"],
        "calls": totals["calls"],
        "cost_is_partial": totals["calls_with_unknown_cost"] > 0,
    }
