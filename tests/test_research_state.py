"""Research State merging: the researcher's corrections are never overwritten."""

from __future__ import annotations

from peerlens.ai_schemas import ExtractedItem, ExtractedRelation, ExtractionResult
from peerlens.models import PaperProject, ResearchBranch, ResearchInput
from peerlens.sections import Confirmation, Provenance, SectionStatus
from peerlens.services import research_state


def make_paper(db) -> PaperProject:
    branch = ResearchBranch(name="Branch")
    db.add(branch)
    db.commit()
    paper = PaperProject(branch_id=branch.id, title="Paper")
    db.add(paper)
    db.commit()
    research_state.ensure_sections(db, paper.id)
    return paper


def extraction(*items: ExtractedItem, coverage: str = "partial") -> ExtractionResult:
    return ExtractionResult(
        section_summary="summary", coverage=coverage, items=list(items)
    )


def item(label: str, statement: str, **kwargs) -> ExtractedItem:
    return ExtractedItem(
        label=label,
        statement=statement,
        provenance=kwargs.pop("provenance", "extracted"),
        details=kwargs.pop("details", {}),
        source_input_ids=kwargs.pop("source_input_ids", []),
        relations=kwargs.pop("relations", []),
    )


def test_ensure_sections_is_idempotent(db):
    paper = make_paper(db)
    first = research_state.ensure_sections(db, paper.id)
    second = research_state.ensure_sections(db, paper.id)
    assert len(first) == len(second) == 11


def test_extraction_creates_items_with_provenance(db):
    paper = make_paper(db)
    research_state.apply_extraction(
        db,
        paper.id,
        "hypothesis",
        extraction(item("H1", "Humidity readings improve prediction", source_input_ids=[3])),
    )
    items = research_state.active_items(db, paper.id, "hypothesis")
    assert len(items) == 1
    assert items[0].label == "H1"
    assert items[0].provenance == Provenance.EXTRACTED.value
    assert items[0].confirmation == Confirmation.UNCONFIRMED.value
    assert items[0].source_input_ids == [3]


def test_confirmed_items_survive_re_extraction(db):
    """A researcher's confirmation outranks any later AI extraction."""
    paper = make_paper(db)
    research_state.apply_extraction(db, paper.id, "hypothesis", extraction(item("H1", "Original")))
    stored = research_state.active_items(db, paper.id, "hypothesis")[0]
    stored.confirmation = Confirmation.CONFIRMED.value
    db.commit()

    stats = research_state.apply_extraction(
        db, paper.id, "hypothesis", extraction(item("H1", "AI rewrote this", source_input_ids=[9]))
    )
    refreshed = research_state.active_items(db, paper.id, "hypothesis")[0]
    assert refreshed.statement == "Original"
    assert stats["protected"] == 1
    # Sources still widen, because that is additive information, not a rewrite.
    assert 9 in refreshed.source_input_ids


def test_edited_items_survive_re_extraction(db):
    paper = make_paper(db)
    research_state.apply_extraction(db, paper.id, "results", extraction(item("R1", "2.1 C")))
    stored = research_state.active_items(db, paper.id, "results")[0]
    stored.statement = "2.1 C (mean of 3 runs)"
    stored.confirmation = Confirmation.EDITED.value
    db.commit()

    research_state.apply_extraction(db, paper.id, "results", extraction(item("R1", "2.1 C")))
    assert research_state.active_items(db, paper.id, "results")[0].statement.endswith("3 runs)")


def test_rejected_items_are_not_resurrected(db):
    paper = make_paper(db)
    research_state.apply_extraction(db, paper.id, "findings", extraction(item("F1", "Overreach")))
    stored = research_state.active_items(db, paper.id, "findings")[0]
    stored.confirmation = Confirmation.REJECTED.value
    stored.active = False
    db.commit()

    research_state.apply_extraction(db, paper.id, "findings", extraction(item("F1", "Overreach")))
    assert research_state.active_items(db, paper.id, "findings") == []


def test_unconfirmed_items_are_deactivated_when_no_longer_supported(db):
    paper = make_paper(db)
    research_state.apply_extraction(
        db, paper.id, "experiments", extraction(item("E1", "one"), item("E2", "two"))
    )
    research_state.apply_extraction(db, paper.id, "experiments", extraction(item("E1", "one")))
    labels = [i.label for i in research_state.active_items(db, paper.id, "experiments")]
    assert labels == ["E1"]


def test_relationships_only_link_existing_items(db):
    paper = make_paper(db)
    research_state.apply_extraction(db, paper.id, "experiments", extraction(item("E4", "ablation")))
    research_state.apply_extraction(
        db,
        paper.id,
        "hypothesis",
        extraction(
            item(
                "H1",
                "humidity readings help",
                relations=[
                    ExtractedRelation(rel_type="tested_by", target_label="E4"),
                    # A dangling reference must be dropped, never invented into existence.
                    ExtractedRelation(rel_type="tested_by", target_label="E99"),
                ],
            )
        ),
    )
    rendered = research_state.render_full_state(db, paper.id)
    assert "H1 --tested_by--> E4" in rendered
    assert "E99" not in rendered


def test_new_results_demote_ready_dependents(db):
    """A READY section returns to NEEDS ATTENTION when its evidence changes."""
    paper = make_paper(db)
    findings = research_state.get_section(db, paper.id, "findings")
    findings.status = SectionStatus.READY.value
    findings.summary = "settled"
    db.commit()

    affected = research_state.mark_dependents_stale(db, paper.id, "results", "new results added")
    assert "findings" in affected
    refreshed = research_state.get_section(db, paper.id, "findings")
    assert refreshed.status == SectionStatus.NEEDS_ATTENTION.value
    assert refreshed.needs_recheck is True


def test_rendered_state_exposes_provenance_and_sources(db):
    paper = make_paper(db)
    db.add(ResearchInput(paper_id=paper.id, label="note", content="text"))
    db.commit()
    research_state.apply_extraction(
        db,
        paper.id,
        "hypothesis",
        extraction(item("H1", "claimed", provenance="inferred", source_input_ids=[1])),
    )
    rendered = research_state.render_section_state(db, paper.id, "hypothesis")
    assert "inferred" in rendered
    assert "#1" in rendered


def test_render_material_marks_empty_state_honestly(db):
    paper = make_paper(db)
    assert "No research material" in research_state.render_research_material(db, paper.id)
