"""AI usage aggregation.

Unknown values stay unknown. A token count that a provider did not report is
never estimated, and a cost that cannot be derived is reported as ``null``
rather than as zero.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AIUsageEvent, PaperProject, ResearchBranch

GROUPABLE = {
    "operation": AIUsageEvent.operation,
    "provider": AIUsageEvent.provider,
    "model": AIUsageEvent.model,
    "paper": AIUsageEvent.paper_id,
    "branch": AIUsageEvent.branch_id,
    "location": AIUsageEvent.is_local,
}


def _base_filters(query, paper_id: int | None, branch_id: int | None, since_days: int | None):
    if paper_id is not None:
        query = query.where(AIUsageEvent.paper_id == paper_id)
    if branch_id is not None:
        query = query.where(AIUsageEvent.branch_id == branch_id)
    if since_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        query = query.where(AIUsageEvent.created_at >= cutoff.replace(tzinfo=None))
    return query


def totals(
    db: Session,
    paper_id: int | None = None,
    branch_id: int | None = None,
    since_days: int | None = None,
) -> dict:
    query = _base_filters(
        select(
            func.count(AIUsageEvent.id),
            func.sum(AIUsageEvent.input_tokens),
            func.sum(AIUsageEvent.output_tokens),
            func.sum(AIUsageEvent.cached_tokens),
            func.sum(AIUsageEvent.estimated_cost),
            func.avg(AIUsageEvent.latency_ms),
        ),
        paper_id,
        branch_id,
        since_days,
    )
    calls, input_tokens, output_tokens, cached, cost, latency = db.execute(query).one()

    unknown_cost = db.scalar(
        _base_filters(
            select(func.count(AIUsageEvent.id)).where(AIUsageEvent.estimated_cost.is_(None)),
            paper_id,
            branch_id,
            since_days,
        )
    )
    failures = db.scalar(
        _base_filters(
            select(func.count(AIUsageEvent.id)).where(AIUsageEvent.success.is_(False)),
            paper_id,
            branch_id,
            since_days,
        )
    )

    return {
        "calls": calls or 0,
        "input_tokens": int(input_tokens) if input_tokens is not None else None,
        "output_tokens": int(output_tokens) if output_tokens is not None else None,
        "cached_tokens": int(cached) if cached is not None else None,
        "total_tokens": (
            int((input_tokens or 0) + (output_tokens or 0))
            if (input_tokens is not None or output_tokens is not None)
            else None
        ),
        "estimated_cost": round(float(cost), 6) if cost is not None else None,
        "calls_with_unknown_cost": unknown_cost or 0,
        "failed_calls": failures or 0,
        "avg_latency_ms": int(latency) if latency is not None else None,
    }


def breakdown(
    db: Session,
    dimension: str,
    paper_id: int | None = None,
    branch_id: int | None = None,
    since_days: int | None = None,
) -> list[dict]:
    column = GROUPABLE.get(dimension)
    if column is None:
        raise ValueError(f"Cannot group usage by {dimension!r}")

    query = _base_filters(
        select(
            column,
            func.count(AIUsageEvent.id),
            func.sum(AIUsageEvent.input_tokens),
            func.sum(AIUsageEvent.output_tokens),
            func.sum(AIUsageEvent.estimated_cost),
        ).group_by(column),
        paper_id,
        branch_id,
        since_days,
    )

    paper_names: dict[int, str] = {}
    branch_names: dict[int, str] = {}
    if dimension == "paper":
        paper_names = {p.id: p.title for p in db.scalars(select(PaperProject))}
    if dimension == "branch":
        branch_names = {b.id: b.name for b in db.scalars(select(ResearchBranch))}

    rows: list[dict] = []
    for key, calls, input_tokens, output_tokens, cost in db.execute(query).all():
        if dimension == "paper":
            label = paper_names.get(key, "(deleted paper)") if key else "(not paper-specific)"
        elif dimension == "branch":
            label = branch_names.get(key, "(deleted branch)") if key else "(not branch-specific)"
        elif dimension == "location":
            label = "local" if key else "cloud"
        else:
            label = str(key)
        rows.append(
            {
                "key": label,
                "calls": calls,
                "input_tokens": int(input_tokens) if input_tokens is not None else None,
                "output_tokens": int(output_tokens) if output_tokens is not None else None,
                "total_tokens": int((input_tokens or 0) + (output_tokens or 0))
                if (input_tokens is not None or output_tokens is not None)
                else None,
                "estimated_cost": round(float(cost), 6) if cost is not None else None,
            }
        )
    rows.sort(key=lambda r: (r["total_tokens"] or 0), reverse=True)
    return rows


def last_event_meta(db: Session, paper_id: int, operation: str | None = None) -> dict | None:
    """Reproducibility metadata for the most recent call on this paper.

    Which provider and model produced an analysis is part of the record. Token
    counts the provider did not report stay ``null`` — never estimated.
    """
    from ..llm.client import task_type_for

    query = select(AIUsageEvent).where(AIUsageEvent.paper_id == paper_id)
    if operation is not None:
        query = query.where(AIUsageEvent.operation == operation)
    event = db.scalars(
        query.order_by(AIUsageEvent.created_at.desc(), AIUsageEvent.id.desc()).limit(1)
    ).first()
    if event is None:
        return None
    return {
        "task_type": task_type_for(event.operation),
        "operation": event.operation,
        "provider": event.provider,
        "model": event.model or None,
        "created_at": event.created_at.isoformat(),
        "duration_ms": event.latency_ms,
        "usage": {
            "input_tokens": event.input_tokens,
            "output_tokens": event.output_tokens,
            "cached_tokens": event.cached_tokens,
        },
    }


def recent_events(db: Session, limit: int = 100, paper_id: int | None = None) -> list[AIUsageEvent]:
    query = select(AIUsageEvent).order_by(AIUsageEvent.created_at.desc()).limit(limit)
    if paper_id is not None:
        query = query.where(AIUsageEvent.paper_id == paper_id)
    return list(db.scalars(query))
