"""Literature: OpenAlex search, manual entry, and relevance analysis.

PeerLens is not a citation manager. It stores enough about each reference to
assess the state of the art honestly, and it never fabricates a reference.
"""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai_schemas import LiteratureRelevance
from ..config import OPENALEX_MAILTO
from ..llm import client
from ..models import LiteratureItem, PaperLiterature, PaperProject
from ..prompts_loader import global_prompt
from . import research_state

logger = logging.getLogger("peerlens.literature")

OPENALEX_BASE = "https://api.openalex.org"


class LiteratureSearchError(RuntimeError):
    pass


def _reconstruct_abstract(inverted_index: dict | None) -> str:
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the text."""
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, indices in inverted_index.items():
        for index in indices or []:
            positions.append((index, word))
    if not positions:
        return ""
    positions.sort(key=lambda pair: pair[0])
    return " ".join(word for _, word in positions)


def _normalise_work(work: dict) -> dict:
    doi = (work.get("doi") or "").replace("https://doi.org/", "") or None
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    authors = [
        (a.get("author") or {}).get("display_name", "")
        for a in work.get("authorships", [])
    ]
    url = (
        location.get("landing_page_url")
        or (work.get("open_access") or {}).get("oa_url")
        or (f"https://doi.org/{doi}" if doi else work.get("id"))
    )
    return {
        "external_id": work.get("id"),
        "title": work.get("display_name") or work.get("title") or "(untitled)",
        "authors": [a for a in authors if a],
        "year": work.get("publication_year"),
        "doi": doi,
        "abstract": _reconstruct_abstract(work.get("abstract_inverted_index")),
        "venue": source.get("display_name") or "",
        "url": url,
        "cited_by_count": work.get("cited_by_count"),
        "source": "openalex",
        "verification_status": "verified",
    }


async def search_openalex(query: str, limit: int = 15) -> list[dict]:
    """Search OpenAlex. Returns only what the API actually returned."""
    params: dict[str, str | int] = {
        "search": query,
        "per-page": max(1, min(limit, 50)),
        "select": (
            "id,display_name,publication_year,doi,authorships,abstract_inverted_index,"
            "primary_location,open_access,cited_by_count"
        ),
    }
    if OPENALEX_MAILTO:
        params["mailto"] = OPENALEX_MAILTO
    headers = {"User-Agent": f"PeerLens ({OPENALEX_MAILTO or 'open-source research tool'})"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as http:
            response = await http.get(f"{OPENALEX_BASE}/works", params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise LiteratureSearchError(f"OpenAlex search failed: {exc}") from exc
    return [_normalise_work(work) for work in data.get("results", [])]


async def fetch_by_doi(doi: str) -> dict | None:
    clean = doi.strip().replace("https://doi.org/", "").replace("doi:", "")
    params = {"mailto": OPENALEX_MAILTO} if OPENALEX_MAILTO else {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as http:
            response = await http.get(f"{OPENALEX_BASE}/works/doi:{clean}", params=params)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return _normalise_work(response.json())
    except httpx.HTTPError as exc:
        raise LiteratureSearchError(f"DOI lookup failed: {exc}") from exc


def attach_to_paper(db: Session, literature_id: int, paper_id: int, note: str = "") -> None:
    existing = db.scalar(
        select(PaperLiterature).where(
            PaperLiterature.paper_id == paper_id,
            PaperLiterature.literature_id == literature_id,
        )
    )
    if existing is None:
        db.add(PaperLiterature(paper_id=paper_id, literature_id=literature_id, note=note))
        db.commit()
    elif note:
        existing.note = note
        db.commit()


def render_library(db: Session, branch_id: int, paper_id: int | None = None) -> str:
    query = select(LiteratureItem).where(LiteratureItem.branch_id == branch_id)
    items = list(db.scalars(query))
    if not items:
        return "(The literature library is empty.)"
    attached: set[int] = set()
    if paper_id is not None:
        attached = {
            row.literature_id
            for row in db.scalars(
                select(PaperLiterature).where(PaperLiterature.paper_id == paper_id)
            )
        }
    lines = []
    for item in items:
        authors = ", ".join(item.authors[:3]) if item.authors else "unknown authors"
        flag = " [attached to this paper]" if item.id in attached else ""
        head = (
            f"- [L{item.id}] {authors}. {item.title}. "
            f"{item.year or 'year unknown'}. {item.venue or ''} "
            f"(source: {item.source}, verification: {item.verification_status}){flag}"
        )
        lines.append(head.strip())
        if item.abstract:
            lines.append(f"    abstract: {item.abstract[:1200]}")
        if item.relation_to_research:
            lines.append(f"    researcher's note: {item.relation_to_research}")
    return "\n".join(lines)


async def analyze_literature(db: Session, paper: PaperProject) -> LiteratureRelevance:
    user_message = "\n\n".join(
        [
            research_state.paper_context_header(paper),
            "# Current Research State\n"
            + research_state.render_full_state(db, paper.id, include_relationships=False),
            "# Literature library (the only references you may use)\n"
            + render_library(db, paper.branch_id, paper.id),
            "# Your task\nAssess this literature against the current research. Use only "
            "the references listed above.",
        ]
    )
    result, _ = await client.run_structured(
        db,
        operation="literature_analysis",
        system=global_prompt("literature_analysis"),
        user=user_message,
        schema=LiteratureRelevance,
        paper_id=paper.id,
        branch_id=paper.branch_id,
        max_tokens=6000,
        temperature=0.1,
    )
    return result
