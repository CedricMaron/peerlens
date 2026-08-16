"""Structural validation of the eval cases. Runs in CI without any model."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from run_evals import SEVERITY_RANK, grade, load_cases, worst_severity  # noqa: E402

CASES = load_cases()

# The ten defect classes the product claims to detect (spec section 18).
REQUIRED_CASE_IDS = {
    "universal_claim_one_dataset",
    "significance_without_statistics",
    "confounded_experiment",
    "missing_important_baseline",
    "novelty_from_failed_search",
    "conclusion_stronger_than_evidence",
    "ignored_negative_result",
    "methodology_cannot_test_hypothesis",
    "finding_unsupported_by_results",
    "contribution_covered_by_prior_work",
}


def test_all_required_defect_classes_are_covered():
    assert REQUIRED_CASE_IDS.issubset({case["id"] for case in CASES})


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_is_well_formed(case):
    from peerlens.sections import SECTION_KEYS

    assert case["id"] and case["description"]
    assert case["inputs"] and all(entry["content"].strip() for entry in case["inputs"])

    target = case["target"]
    assert target["kind"] in ("section_review", "challenge")
    if target["kind"] == "section_review":
        assert target["section"] in SECTION_KEYS

    expect = case["expect"]
    assert expect["signals"], "a case must assert at least one signal"
    for signal in expect["signals"]:
        assert signal["name"]
        assert signal["any"], "a signal needs at least one alternative pattern"
    for forbidden in expect.get("forbidden", []):
        assert forbidden["name"] and forbidden["any"]
    if "min_severity" in expect:
        assert expect["min_severity"] in SEVERITY_RANK


def test_case_ids_are_unique():
    ids = [case["id"] for case in CASES]
    assert len(ids) == len(set(ids))


def test_worst_severity_picks_the_most_severe():
    assert worst_severity([{"severity": "minor"}, {"severity": "blocker"}]) == "blocker"
    assert worst_severity([]) == "none"


def test_grading_detects_a_matching_signal():
    case = {
        "id": "t",
        "expect": {
            "min_severity": "major",
            "signals": [{"name": "finds confound", "any": ["confound", "two factors"]}],
            "forbidden": [{"name": "praise", "any": ["impressive"]}],
        },
    }
    payload = {
        "issues": [
            {"severity": "major", "issue": "E4 varies two factors at once.", "evidence": "E4"}
        ]
    }
    result = grade(case, payload)
    assert result.passed
    assert result.matched == ["finds confound"]


def test_grading_flags_missed_signals_and_low_severity():
    case = {
        "id": "t",
        "expect": {
            "min_severity": "blocker",
            "signals": [{"name": "finds confound", "any": ["confound"]}],
        },
    }
    result = grade(case, {"issues": [{"severity": "minor", "issue": "wording could improve"}]})
    assert not result.passed
    assert result.missed == ["finds confound"]
    assert result.severity_ok is False


def test_grading_flags_forbidden_content():
    case = {
        "id": "t",
        "expect": {
            "signals": [{"name": "s", "any": ["confound"]}],
            "forbidden": [{"name": "endorses novelty", "any": ["no prior work exists"]}],
        },
    }
    payload = {"issues": [{"issue": "confound present"}], "summary": "No prior work exists here."}
    result = grade(case, payload)
    assert result.violated == ["endorses novelty"]
    assert not result.passed
