"""The checklist definition and the scientific prompts behind it."""

from __future__ import annotations

import pytest

from peerlens import prompts_loader
from peerlens.sections import (
    REQUIRED_SECTION_KEYS,
    SECTION_ITEM_TYPES,
    SECTION_KEYS,
    dependents_of,
)


def test_eleven_sections_in_order():
    assert len(SECTION_KEYS) == 11
    assert SECTION_KEYS[0] == "problem"
    assert SECTION_KEYS[-1] == "limitations"
    assert set(SECTION_ITEM_TYPES) == set(SECTION_KEYS)
    assert REQUIRED_SECTION_KEYS == SECTION_KEYS


def test_new_results_propagate_forward():
    """New results must invalidate everything downstream of them."""
    downstream = dependents_of("results")
    for key in ("findings", "contribution", "limitations"):
        assert key in downstream
    # ... but never backwards: adding results does not invalidate the problem.
    for key in ("problem", "literature", "gap", "question"):
        assert key not in downstream


def test_dependency_graph_is_acyclic():
    for key in SECTION_KEYS:
        assert key not in dependents_of(key), f"{key} depends on itself transitively"


def test_limitations_is_terminal():
    assert dependents_of("limitations") == []


@pytest.mark.parametrize("section", SECTION_KEYS)
def test_every_section_has_both_specialized_prompts(section):
    """No generic prompt reuse: each section is reviewed on its own terms."""
    extract = prompts_loader.section_prompt(section, "extract")
    review = prompts_loader.section_prompt(section, "review")
    assert len(extract) > 800
    assert len(review) > 800
    assert extract != review


def test_prompts_are_section_specific():
    """Two different sections must not produce the same review prompt."""
    reviews = {key: prompts_loader.section_prompt(key, "review") for key in SECTION_KEYS}
    assert len(set(reviews.values())) == len(SECTION_KEYS)


def _flat(text: str) -> str:
    """Compare on content, not on how the Markdown happens to wrap."""
    return " ".join(text.lower().split())


def test_shared_rules_are_included_everywhere():
    for key in SECTION_KEYS:
        for kind in ("extract", "review"):
            prompt = _flat(prompts_loader.section_prompt(key, kind))
            assert "invent facts" in prompt
            assert "prefer explicit uncertainty" in prompt


def test_global_prompts_exist():
    for name in ("challenge_research", "compile_manuscript", "literature_analysis"):
        assert len(prompts_loader.global_prompt(name)) > 800


def test_novelty_rule_present_where_it_matters():
    """The "absence of search is not novelty" rule must reach the right prompts."""
    phrase = "no equivalent work was identified"
    for name in ("gap", "contribution", "literature"):
        assert phrase in _flat(prompts_loader.section_prompt(name, "review"))
    assert phrase in _flat(prompts_loader.global_prompt("literature_analysis"))


def test_unknown_section_rejected():
    with pytest.raises(prompts_loader.PromptNotFound):
        prompts_loader.section_prompt("not_a_section", "extract")


def test_available_prompts_covers_all_sections():
    available = prompts_loader.available_prompts()
    assert len(available["checklist"]) == 22
    assert "challenge_research.md" in available["global"]
