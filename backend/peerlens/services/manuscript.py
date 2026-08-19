"""Manuscript compilation: assembly over reviewed Research State.

This is the last step, not the goal. It writes up what the research already
supports and refuses to invent what it does not.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai_schemas import ManuscriptResult
from ..llm import client
from ..models import LiteratureItem, Manuscript, PaperLiterature, PaperProject
from ..prompts_loader import global_prompt
from . import research_state
from .readiness import compile_gate


class ManuscriptLocked(RuntimeError):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__(" ".join(reasons))


def render_verified_literature(db: Session, paper_id: int) -> str:
    """Only references actually in the library, with their verification status."""
    rows = list(
        db.execute(
            select(LiteratureItem, PaperLiterature)
            .join(PaperLiterature, PaperLiterature.literature_id == LiteratureItem.id)
            .where(PaperLiterature.paper_id == paper_id)
        )
    )
    if not rows:
        return (
            "(No references are attached to this paper project. Do not cite anything; "
            "record the absence in content_gaps.)"
        )
    lines = []
    for literature, link in rows:
        authors = ", ".join(literature.authors[:4]) if literature.authors else "unknown authors"
        if literature.authors and len(literature.authors) > 4:
            authors += " et al."
        parts = [f"- [L{literature.id}] {authors}. {literature.title}."]
        if literature.year:
            parts.append(f"{literature.year}.")
        if literature.venue:
            parts.append(f"{literature.venue}.")
        if literature.doi:
            parts.append(f"DOI: {literature.doi}.")
        parts.append(f"(verification: {literature.verification_status})")
        if link.note:
            parts.append(f"Note: {link.note}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def to_markdown(result: ManuscriptResult) -> str:
    parts = [f"# {result.title}", ""]
    for section in result.sections:
        parts.append(f"## {section.heading}")
        parts.append("")
        parts.append(section.markdown.strip())
        parts.append("")
    if result.content_gaps:
        parts.append("---")
        parts.append("")
        parts.append("## Content gaps flagged during compilation")
        parts.append("")
        parts.append(
            "_These are places where the reviewed Research State did not contain "
            "enough material. They were not filled in._"
        )
        parts.append("")
        parts.extend(f"- {gap}" for gap in result.content_gaps)
        parts.append("")
    return "\n".join(parts)


async def compile_manuscript(
    db: Session, paper: PaperProject, force: bool = False
) -> Manuscript:
    gate = compile_gate(db, paper.id)
    if not gate["can_compile"] and not force:
        raise ManuscriptLocked(gate["reasons"])

    user_message = "\n\n".join(
        [
            research_state.paper_context_header(paper),
            "# Reviewed Research State\n" + research_state.render_full_state(db, paper.id),
            "# Verified references available for citation\n"
            + render_verified_literature(db, paper.id),
            "# Research material (verbatim, for exact values and wording)\n"
            + research_state.render_research_material(db, paper.id, char_budget=80_000),
            "# Your task\nCompile the manuscript from the reviewed Research State above. "
            "Report values exactly as supplied. Preserve claim strength, uncertainty, "
            "negative results and limitations. Record shortfalls in content_gaps rather "
            "than filling them.",
        ]
    )

    result, llm_result = await client.run_structured(
        db,
        operation="compile_manuscript",
        system=global_prompt("compile_manuscript"),
        user=user_message,
        schema=ManuscriptResult,
        paper_id=paper.id,
        branch_id=paper.branch_id,
        max_tokens=16000,
        temperature=0.3,
    )

    manuscript = Manuscript(
        paper_id=paper.id,
        title=result.title or paper.title,
        markdown=to_markdown(result),
        sections={
            "sections": [s.model_dump() for s in result.sections],
            "content_gaps": result.content_gaps,
            # Reproducibility: which provider and model wrote this manuscript.
            "generation": client.run_metadata(llm_result, "compile_manuscript"),
        },
    )
    db.add(manuscript)
    db.commit()
    return manuscript
