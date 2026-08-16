"""Pydantic schemas for the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Branches and papers
# --------------------------------------------------------------------------

class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = ""


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None


class PaperSummary(ORMModel):
    id: int
    branch_id: int
    title: str
    notes: str
    created_at: datetime
    updated_at: datetime


class BranchOut(ORMModel):
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    papers: list[PaperSummary] = []
    literature_count: int = 0


class PaperCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    notes: str = ""


class PaperUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    notes: str | None = None


# --------------------------------------------------------------------------
# Research inputs
# --------------------------------------------------------------------------

class ResearchInputCreate(BaseModel):
    label: str = ""
    content: str = Field(min_length=1)


class ResearchInputOut(ORMModel):
    id: int
    paper_id: int
    label: str
    kind: str
    content: str
    original_filename: str | None
    content_type: str | None
    byte_size: int
    extraction_note: str
    created_at: datetime
    analyzed_at: datetime | None


class ResearchInputListItem(ORMModel):
    """Inputs without their full text, for list views."""

    id: int
    label: str
    kind: str
    original_filename: str | None
    byte_size: int
    extraction_note: str
    char_count: int = 0
    created_at: datetime
    analyzed_at: datetime | None
    preview: str = ""


# --------------------------------------------------------------------------
# Checklist
# --------------------------------------------------------------------------

class IssueOutSchema(ORMModel):
    id: int
    section_key: str | None
    origin: str
    severity: str
    issue: str
    why_it_matters: str
    evidence: str
    recommended_action: str
    affected_sections: list[str]
    status: str
    created_at: datetime


class ResearchItemOut(ORMModel):
    id: int
    section_key: str
    item_type: str
    label: str
    statement: str
    details: dict[str, Any]
    provenance: str
    confirmation: str
    source_input_ids: list[int]
    order_index: int
    updated_at: datetime


class RelationshipOut(BaseModel):
    id: int
    rel_type: str
    rationale: str
    source_label: str
    target_label: str
    source_section: str
    target_section: str


class SectionOverview(BaseModel):
    key: str
    number: int
    title: str
    purpose: str
    status: str
    summary: str
    needs_recheck: bool
    recheck_reason: str
    item_count: int
    issue_counts: dict[str, int]
    missing_count: int
    depends_on: list[str]
    last_extracted_at: datetime | None
    last_reviewed_at: datetime | None


class CompileGate(BaseModel):
    can_compile: bool
    reasons: list[str]
    ready_sections: int
    required_sections: int
    open_blockers: int


class ReadinessOut(BaseModel):
    sections: list[SectionOverview]
    gate: CompileGate
    status_counts: dict[str, int]


class SectionDetailOut(BaseModel):
    key: str
    number: int
    title: str
    purpose: str
    status: str
    summary: str
    needs_recheck: bool
    recheck_reason: str
    checks: list[dict[str, Any]]
    missing_information: list[dict[str, Any]]
    items: list[ResearchItemOut]
    issues: list[IssueOutSchema]
    relationships: list[RelationshipOut]
    sources: list[ResearchInputListItem]
    depends_on: list[str]
    last_extracted_at: datetime | None
    last_reviewed_at: datetime | None


class ItemUpdate(BaseModel):
    statement: str | None = None
    details: dict[str, str] | None = None
    label: str | None = None


class ItemCreate(BaseModel):
    section_key: str
    label: str = ""
    statement: str = Field(min_length=1)
    details: dict[str, str] = Field(default_factory=dict)


class IssueStatusUpdate(BaseModel):
    status: Literal["open", "resolved", "dismissed"]


class AnalyzeRequest(BaseModel):
    sections: list[str] | None = None
    run_review: bool = True


class AnalyzeResponse(BaseModel):
    extracted: dict[str, Any]
    reviewed: list[str]
    errors: dict[str, str]
    readiness: ReadinessOut


class ChallengeOut(BaseModel):
    overall_assessment: str
    cross_section_observations: list[str]
    issues: list[IssueOutSchema]


# --------------------------------------------------------------------------
# Literature
# --------------------------------------------------------------------------

class LiteratureSearchResult(BaseModel):
    external_id: str | None = None
    title: str
    authors: list[str] = []
    year: int | None = None
    doi: str | None = None
    abstract: str = ""
    venue: str = ""
    url: str | None = None
    cited_by_count: int | None = None
    source: str = "openalex"
    verification_status: str = "verified"
    already_in_library: bool = False


class LiteratureCreate(BaseModel):
    title: str = Field(min_length=1)
    authors: list[str] = []
    year: int | None = None
    doi: str | None = None
    abstract: str = ""
    venue: str = ""
    url: str | None = None
    source: str = "manual"
    external_id: str | None = None
    verification_status: str = "unverified"
    relation_to_research: str = ""
    relation_kind: str = "related"
    paper_id: int | None = None


class LiteratureUpdate(BaseModel):
    relation_to_research: str | None = None
    relation_kind: str | None = None
    verification_status: str | None = None


class LiteratureOut(ORMModel):
    id: int
    branch_id: int
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    abstract: str
    url: str | None
    venue: str
    source: str
    verification_status: str
    relation_to_research: str
    relation_kind: str
    created_at: datetime
    attached_paper_ids: list[int] = []


class LiteratureAnalysisOut(BaseModel):
    closest_prior_work: list[str]
    existing_approaches: list[str]
    important_baselines: list[str]
    known_limitations: list[str]
    contradictory_results: list[str]
    relation_to_current_work: str
    search_caveat: str


# --------------------------------------------------------------------------
# Manuscript
# --------------------------------------------------------------------------

class ManuscriptOut(ORMModel):
    id: int
    paper_id: int
    title: str
    markdown: str
    sections: dict[str, Any]
    created_at: datetime


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

class ProviderSettingsIn(BaseModel):
    provider: Literal["openai", "anthropic", "ollama"]
    model: str = Field(min_length=1)
    api_key: str | None = None
    base_url: str | None = None


class ProviderSettingsOut(BaseModel):
    provider: str
    model: str
    base_url: str
    api_key_hint: str
    api_key_set: bool
    from_environment: bool
    configured: bool
    defaults: dict[str, Any]


class TestConnectionRequest(BaseModel):
    provider: Literal["openai", "anthropic", "ollama"] | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None


class TestConnectionResult(BaseModel):
    ok: bool
    message: str


# --------------------------------------------------------------------------
# Usage
# --------------------------------------------------------------------------

class UsageTotals(BaseModel):
    calls: int
    input_tokens: int | None
    output_tokens: int | None
    cached_tokens: int | None
    total_tokens: int | None
    estimated_cost: float | None
    calls_with_unknown_cost: int
    failed_calls: int
    avg_latency_ms: int | None


class UsageBreakdownRow(BaseModel):
    key: str
    calls: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost: float | None


class UsageEventOut(ORMModel):
    id: int
    created_at: datetime
    paper_id: int | None
    operation: str
    provider: str
    model: str
    is_local: bool
    input_tokens: int | None
    output_tokens: int | None
    cached_tokens: int | None
    latency_ms: int | None
    estimated_cost: float | None
    success: bool
    error: str | None


class UsageOverview(BaseModel):
    totals: UsageTotals
    by_operation: list[UsageBreakdownRow]
    by_provider: list[UsageBreakdownRow]
    by_model: list[UsageBreakdownRow]
    by_paper: list[UsageBreakdownRow]
    by_branch: list[UsageBreakdownRow]
    by_location: list[UsageBreakdownRow]
    recent: list[UsageEventOut]
