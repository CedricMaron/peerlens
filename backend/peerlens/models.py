"""SQLAlchemy models: research branches, papers, raw inputs, research state.

Design notes
------------
* Raw research input is *never* mutated or discarded. Everything the AI derives
  points back at the ``ResearchInput`` rows it came from.
* Scientific entities (results, findings, claims, ...) live in ``ResearchItem``
  and are linked by ``Relationship`` rows. SQLite is sufficient for V1; no
  graph database is introduced.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .sections import Confirmation, Provenance, SectionStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ResearchBranch(Base):
    """A line of research that may produce several related papers."""

    __tablename__ = "research_branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    papers: Mapped[list["PaperProject"]] = relationship(
        back_populates="branch", cascade="all, delete-orphan", order_by="PaperProject.id"
    )
    literature: Mapped[list["LiteratureItem"]] = relationship(
        back_populates="branch", cascade="all, delete-orphan"
    )


class PaperProject(Base):
    """A single manuscript-in-progress inside a research branch."""

    __tablename__ = "paper_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("research_branches.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    branch: Mapped[ResearchBranch] = relationship(back_populates="papers")
    inputs: Mapped[list["ResearchInput"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", order_by="ResearchInput.id"
    )
    sections: Mapped[list["SectionState"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )
    items: Mapped[list["ResearchItem"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )
    issues: Mapped[list["Issue"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )


class ResearchInput(Base):
    """Free-form research material, preserved verbatim, forever."""

    __tablename__ = "research_inputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("paper_projects.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(300), default="")
    kind: Mapped[str] = mapped_column(String(20), default="text")  # text | file
    content: Mapped[str] = mapped_column(Text, default="")  # extracted plain text
    original_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stored_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    extraction_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    paper: Mapped[PaperProject] = relationship(back_populates="inputs")

    @property
    def citation(self) -> str:
        base = self.label or self.original_filename or f"Input #{self.id}"
        return f"[{self.id}] {base}"


class SectionState(Base):
    """Per-section checklist status, review output and staleness tracking."""

    __tablename__ = "section_states"
    __table_args__ = (UniqueConstraint("paper_id", "key", name="uq_section_per_paper"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("paper_projects.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=SectionStatus.MISSING.value)
    summary: Mapped[str] = mapped_column(Text, default="")
    checks: Mapped[list] = mapped_column(JSON, default=list)
    missing_information: Mapped[list] = mapped_column(JSON, default=list)
    needs_recheck: Mapped[bool] = mapped_column(Boolean, default=False)
    recheck_reason: Mapped[str] = mapped_column(Text, default="")
    last_extracted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    paper: Mapped[PaperProject] = relationship(back_populates="sections")


class ResearchItem(Base):
    """One scientific entity in the Research State.

    A hypothesis, an experiment, a result, a finding, a claim -- each carries
    its provenance and the researcher's confirmation decision.
    """

    __tablename__ = "research_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("paper_projects.id", ondelete="CASCADE"), index=True
    )
    section_key: Mapped[str] = mapped_column(String(40), index=True)
    item_type: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80), default="")  # e.g. "H1", "E4"
    statement: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)  # scope, variables, ...
    provenance: Mapped[str] = mapped_column(String(20), default=Provenance.EXTRACTED.value)
    confirmation: Mapped[str] = mapped_column(
        String(20), default=Confirmation.UNCONFIRMED.value
    )
    source_input_ids: Mapped[list] = mapped_column(JSON, default=list)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    paper: Mapped[PaperProject] = relationship(back_populates="items")


class Relationship(Base):
    """A scientific relationship between two research items."""

    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("paper_projects.id", ondelete="CASCADE"), index=True
    )
    source_item_id: Mapped[int] = mapped_column(
        ForeignKey("research_items.id", ondelete="CASCADE"), index=True
    )
    target_item_id: Mapped[int] = mapped_column(
        ForeignKey("research_items.id", ondelete="CASCADE"), index=True
    )
    rel_type: Mapped[str] = mapped_column(String(40))
    rationale: Mapped[str] = mapped_column(Text, default="")
    provenance: Mapped[str] = mapped_column(String(20), default=Provenance.INFERRED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Issue(Base):
    """A scientific weakness raised by a section review or by Challenge."""

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("paper_projects.id", ondelete="CASCADE"), index=True
    )
    section_key: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    origin: Mapped[str] = mapped_column(String(30), default="section_review")
    severity: Mapped[str] = mapped_column(String(20), default="major")
    issue: Mapped[str] = mapped_column(Text)
    why_it_matters: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    affected_sections: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|resolved|dismissed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    paper: Mapped[PaperProject] = relationship(back_populates="issues")


class LiteratureItem(Base):
    """A reference. Never fabricated; verification status is always explicit."""

    __tablename__ = "literature_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("research_branches.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[list] = mapped_column(JSON, default=list)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(300), nullable=True)
    abstract: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    venue: Mapped[str] = mapped_column(String(500), default="")
    source: Mapped[str] = mapped_column(String(40), default="manual")  # openalex|manual|pdf
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified")
    relation_to_research: Mapped[str] = mapped_column(Text, default="")
    relation_kind: Mapped[str] = mapped_column(String(40), default="related")
    stored_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    branch: Mapped[ResearchBranch] = relationship(back_populates="literature")
    links: Mapped[list["PaperLiterature"]] = relationship(
        back_populates="literature", cascade="all, delete-orphan"
    )


class PaperLiterature(Base):
    """Association of a reference with a specific paper project."""

    __tablename__ = "paper_literature"
    __table_args__ = (UniqueConstraint("paper_id", "literature_id", name="uq_paper_lit"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("paper_projects.id", ondelete="CASCADE"), index=True
    )
    literature_id: Mapped[int] = mapped_column(
        ForeignKey("literature_items.id", ondelete="CASCADE"), index=True
    )
    note: Mapped[str] = mapped_column(Text, default="")

    literature: Mapped[LiteratureItem] = relationship(back_populates="links")


class AIUsageEvent(Base):
    """One LLM call. Token counts are stored only when the provider reports them."""

    __tablename__ = "ai_usage_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    paper_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    operation: Mapped[str] = mapped_column(String(80), index=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    model: Mapped[str] = mapped_column(String(120), index=True)
    is_local: Mapped[bool] = mapped_column(Boolean, default=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Manuscript(Base):
    """A compiled manuscript, assembled from reviewed Research State."""

    __tablename__ = "manuscripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("paper_projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(Text, default="")
    markdown: Mapped[str] = mapped_column(Text, default="")
    sections: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AppSetting(Base):
    """Key/value application settings. API keys live here, never in the browser."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
