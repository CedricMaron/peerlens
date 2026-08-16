"""The Research Checklist: section definitions and dependencies.

THE CHECKLIST IS THE PRODUCT. Everything else in PeerLens exists to populate,
review and defend these eleven scientific components.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SectionStatus(str, Enum):
    MISSING = "missing"
    INCOMPLETE = "incomplete"
    NEEDS_ATTENTION = "needs_attention"
    READY = "ready"


class Severity(str, Enum):
    BLOCKER = "blocker"
    MAJOR = "major"
    MINOR = "minor"
    NOTE = "note"


SEVERITY_ORDER = {
    Severity.BLOCKER: 0,
    Severity.MAJOR: 1,
    Severity.MINOR: 2,
    Severity.NOTE: 3,
}


class Provenance(str, Enum):
    """Where a piece of research state came from. Never silently upgraded."""

    PROVIDED = "provided"  # directly provided by the researcher / a source
    EXTRACTED = "extracted"  # AI extracted from supplied material
    INFERRED = "inferred"  # AI interpretation
    SUGGESTED = "suggested"  # AI suggestion, not part of the research yet


class Confirmation(str, Enum):
    UNCONFIRMED = "unconfirmed"
    CONFIRMED = "confirmed"
    EDITED = "edited"
    REJECTED = "rejected"


class RelationType(str, Enum):
    TESTED_BY = "tested_by"  # Hypothesis -> Experiment
    PRODUCES = "produces"  # Experiment -> Result
    SUPPORTS = "supports"  # Result -> Finding, Finding -> Claim, Literature -> ...
    CONTRADICTS = "contradicts"
    CONTRIBUTES_TO = "contributes_to"  # Claim -> Contribution
    ADDRESSES = "addresses"  # Question -> Gap, Methodology -> Question
    ASSUMES = "assumes"  # Claim/Method -> Limitation or assumption


@dataclass(frozen=True)
class SectionDef:
    key: str
    number: int
    title: str
    item_noun: str
    purpose: str
    required_for_manuscript: bool = True
    depends_on: tuple[str, ...] = field(default_factory=tuple)


SECTIONS: tuple[SectionDef, ...] = (
    SectionDef(
        key="problem",
        number=1,
        title="Problem",
        item_noun="problem statement",
        purpose=(
            "The scientific problem the work addresses, why it matters, and its scope."
        ),
    ),
    SectionDef(
        key="literature",
        number=2,
        title="State of the Art",
        item_noun="prior work summary",
        purpose=(
            "Existing approaches, closest prior work, important baselines and "
            "contradictory evidence."
        ),
        depends_on=("problem",),
    ),
    SectionDef(
        key="gap",
        number=3,
        title="Research Gap",
        item_noun="gap statement",
        purpose="What prior work leaves unresolved, and why that matters scientifically.",
        depends_on=("problem", "literature"),
    ),
    SectionDef(
        key="question",
        number=4,
        title="Research Question",
        item_noun="research question",
        purpose="The specific, answerable question the study addresses.",
        depends_on=("gap",),
    ),
    SectionDef(
        key="hypothesis",
        number=5,
        title="Hypothesis",
        item_noun="hypothesis",
        purpose="Falsifiable predictions with identifiable variables and scope.",
        depends_on=("question",),
    ),
    SectionDef(
        key="methodology",
        number=6,
        title="Methodology",
        item_noun="method component",
        purpose="The approach, controls, comparisons and reproducibility conditions.",
        depends_on=("question", "hypothesis"),
    ),
    SectionDef(
        key="experiments",
        number=7,
        title="Experiments",
        item_noun="experiment",
        purpose="Concrete experiments, what each one tests, and its controls/baselines.",
        depends_on=("hypothesis", "methodology"),
    ),
    SectionDef(
        key="results",
        number=8,
        title="Results",
        item_noun="result",
        purpose="Raw observations produced by the experiments, with uncertainty.",
        depends_on=("experiments",),
    ),
    SectionDef(
        key="findings",
        number=9,
        title="Findings",
        item_noun="finding",
        purpose="Interpretations directly supported by the results.",
        depends_on=("results",),
    ),
    SectionDef(
        key="contribution",
        number=10,
        title="Claims & Contribution",
        item_noun="claim",
        purpose="Broader scientific statements and the knowledge the work adds.",
        depends_on=("findings", "literature", "gap"),
    ),
    SectionDef(
        key="limitations",
        number=11,
        title="Limitations",
        item_noun="limitation",
        purpose="Assumptions, untested conditions and the real limits of interpretation.",
        depends_on=("methodology", "experiments", "results", "findings", "contribution"),
    ),
)

SECTION_KEYS: tuple[str, ...] = tuple(s.key for s in SECTIONS)
SECTION_BY_KEY: dict[str, SectionDef] = {s.key: s for s in SECTIONS}
REQUIRED_SECTION_KEYS: tuple[str, ...] = tuple(
    s.key for s in SECTIONS if s.required_for_manuscript
)


def dependents_of(key: str) -> list[str]:
    """Sections that must be re-evaluated when ``key`` changes.

    Research evolves: new results propagate forward to findings, claims,
    contribution and limitations. This is transitive but never cyclic.
    """
    direct = [s.key for s in SECTIONS if key in s.depends_on]
    seen: list[str] = []
    queue = list(direct)
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.append(current)
        queue.extend(s.key for s in SECTIONS if current in s.depends_on)
    return [k for k in SECTION_KEYS if k in seen]


# Models naturally refer to sections by their common names rather than by our
# internal keys. Mapping these back is the difference between a cross-section
# issue linking to the right section and being silently dropped.
SECTION_ALIASES: dict[str, str] = {
    "claim": "contribution",
    "claims": "contribution",
    "claims_and_contribution": "contribution",
    "claims & contribution": "contribution",
    "contributions": "contribution",
    "state_of_the_art": "literature",
    "state of the art": "literature",
    "related_work": "literature",
    "related work": "literature",
    "prior_work": "literature",
    "research_gap": "gap",
    "research gap": "gap",
    "research_question": "question",
    "research question": "question",
    "questions": "question",
    "hypotheses": "hypothesis",
    "method": "methodology",
    "methods": "methodology",
    "experiment": "experiments",
    "experimental_setup": "experiments",
    "result": "results",
    "finding": "findings",
    "limitation": "limitations",
    "problems": "problem",
}


def normalize_section_key(value: str) -> str | None:
    """Resolve a model-supplied section name to a canonical key, or None."""
    if not value:
        return None
    candidate = value.strip().lower().replace("-", "_")
    if candidate in SECTION_BY_KEY:
        return candidate
    return SECTION_ALIASES.get(candidate) or SECTION_ALIASES.get(candidate.replace("_", " "))


# Item types stored in the research state, grouped by the section that owns them.
SECTION_ITEM_TYPES: dict[str, str] = {
    "problem": "problem",
    "literature": "prior_work",
    "gap": "gap",
    "question": "question",
    "hypothesis": "hypothesis",
    "methodology": "method",
    "experiments": "experiment",
    "results": "result",
    "findings": "finding",
    "contribution": "claim",
    "limitations": "limitation",
}
