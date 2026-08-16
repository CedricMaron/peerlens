"""Pydantic schemas for structured LLM output.

These schemas are sent to the model as JSON Schema and used to validate what
comes back. Anything that does not validate is retried once, then surfaced as
an error -- PeerLens never silently accepts malformed scientific output.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Severity = Literal["blocker", "major", "minor", "note"]
CheckStatus = Literal["pass", "fail", "unknown"]
SectionStatusLiteral = Literal["missing", "incomplete", "needs_attention", "ready"]
ProvenanceLiteral = Literal["provided", "extracted", "inferred", "suggested"]
RelationLiteral = Literal[
    "tested_by", "produces", "supports", "contradicts", "contributes_to",
    "addresses", "assumes",
]


def _stringify_mapping(value: Any) -> Any:
    """Models occasionally nest structures inside detail fields; flatten them."""
    if isinstance(value, dict):
        return {
            str(k): (v if isinstance(v, str) else ", ".join(map(str, v)) if isinstance(v, list) else str(v))
            for k, v in value.items()
        }
    return value


class ExtractedRelation(BaseModel):
    rel_type: RelationLiteral
    target_label: str = Field(
        description="Label of the related item, e.g. 'E4' or 'H1'. Must be an item "
        "that exists in this research, never invented."
    )
    rationale: str = ""


class ExtractedItem(BaseModel):
    """One scientific entity extracted from the supplied research material."""

    label: str = Field(description="Short stable label, e.g. 'H1', 'E2', 'R3', 'C1'.")
    statement: str = Field(description="The item itself, stated precisely and concisely.")
    details: dict[str, str] = Field(
        default_factory=dict,
        description="Section-appropriate structured fields, e.g. scope, variables, "
        "expected_effect, baseline, metric, sample_size.",
    )
    provenance: ProvenanceLiteral = Field(
        description="'provided'/'extracted' when stated in the material; 'inferred' "
        "when this is your interpretation; 'suggested' when you are proposing "
        "something the researcher has not stated."
    )
    source_input_ids: list[int] = Field(
        default_factory=list,
        description="IDs of the research inputs this came from. Empty for inferred "
        "or suggested items with no direct source.",
    )
    relations: list[ExtractedRelation] = Field(default_factory=list)

    _flatten_details = field_validator("details", mode="before")(_stringify_mapping)

    @field_validator("source_input_ids", mode="before")
    @classmethod
    def _coerce_ids(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, (int, str)):
            value = [value]
        out: list[int] = []
        for entry in value:
            try:
                out.append(int(str(entry).lstrip("#[").rstrip("]")))
            except (TypeError, ValueError):
                continue
        return out


class ExtractionResult(BaseModel):
    """What the available research tells us about one checklist section."""

    section_summary: str = Field(
        description="A faithful summary of what the material says about this section. "
        "If the material says nothing, say so plainly."
    )
    coverage: Literal["none", "partial", "substantial"] = Field(
        description="How much of this section the supplied material actually covers."
    )
    items: list[ExtractedItem] = Field(default_factory=list)
    notes: str = Field(
        default="",
        description="Optional note about ambiguity or conflicting statements in the material.",
    )


class Check(BaseModel):
    criterion: str = Field(description="The specific scientific criterion assessed.")
    status: CheckStatus
    reason: str = Field(description="Concrete justification referencing the material.")


class IssueOut(BaseModel):
    severity: Severity
    issue: str = Field(description="The specific scientific weakness. Never generic.")
    why_it_matters: str = Field(
        description="The scientific consequence: what conclusion becomes unsafe."
    )
    evidence: str = Field(
        description="What in the supplied research supports this issue, or the precise "
        "absence that does."
    )
    recommended_action: str = Field(
        description="A concrete, actionable step the researcher can take."
    )
    affected_sections: list[str] = Field(default_factory=list)


class MissingInformation(BaseModel):
    item: str = Field(description="Exactly what information is needed.")
    why_needed: str = Field(description="What it would resolve or strengthen.")


class ReviewResult(BaseModel):
    """Is this section scientifically sufficient and defensible?"""

    status: SectionStatusLiteral
    summary: str = Field(description="Two or three sentences. No praise by default.")
    checks: list[Check] = Field(default_factory=list)
    issues: list[IssueOut] = Field(default_factory=list)
    missing_information: list[MissingInformation] = Field(default_factory=list)


class ChallengeResult(BaseModel):
    """Cross-section scientific review of the whole research."""

    overall_assessment: str = Field(
        description="What the research currently supports and what it does not. "
        "Direct and specific; no praise by default."
    )
    issues: list[IssueOut] = Field(
        default_factory=list,
        description="Most important first. Focus on weaknesses that could materially "
        "affect scientific conclusions.",
    )
    cross_section_observations: list[str] = Field(
        default_factory=list,
        description="Contradictions or tensions between sections that are not yet "
        "severe enough to be issues.",
    )


class ManuscriptSection(BaseModel):
    heading: str
    markdown: str


class ManuscriptResult(BaseModel):
    title: str
    sections: list[ManuscriptSection]
    content_gaps: list[str] = Field(
        default_factory=list,
        description="Places where the reviewed Research State did not supply enough "
        "material. State the gap; never fill it with invented content.",
    )


class LiteratureRelevance(BaseModel):
    """Assessment of retrieved literature against the current research."""

    closest_prior_work: list[str] = Field(default_factory=list)
    existing_approaches: list[str] = Field(default_factory=list)
    important_baselines: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)
    contradictory_results: list[str] = Field(default_factory=list)
    relation_to_current_work: str = ""
    search_caveat: str = Field(
        default="",
        description="State the limits of this assessment. Never conclude that no "
        "prior work exists because none was retrieved.",
    )
