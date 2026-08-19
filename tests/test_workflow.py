"""The full product workflow, driven through the HTTP API with a scripted model.

    add research -> understand -> checklist -> review -> weaknesses
    -> correct -> re-check -> challenge -> ready -> compile
"""

from __future__ import annotations

import json

from peerlens.sections import SECTION_KEYS


def extraction_json(label: str, statement: str, coverage: str = "substantial") -> str:
    return json.dumps(
        {
            "section_summary": f"The material describes {statement}.",
            "coverage": coverage,
            "items": [
                {
                    "label": label,
                    "statement": statement,
                    "details": {"scope": "one city, summer only"},
                    "provenance": "extracted",
                    "source_input_ids": [1],
                    "relations": [],
                }
            ],
            "notes": "",
        }
    )


def review_json(status: str, severity: str | None = "major") -> str:
    issues = (
        [
            {
                "severity": severity,
                "issue": "E4 varies the humidity readings and the station count simultaneously.",
                "why_it_matters": "The gain cannot be attributed to the humidity readings.",
                "evidence": "Experiment E4 as described in input #1.",
                "recommended_action": "Run a matched control with the same station count.",
                "affected_sections": ["experiments", "contribution"],
            }
        ]
        if severity
        else []
    )
    return json.dumps(
        {
            "status": status,
            "summary": "Assessed against the section criteria.",
            "checks": [
                {"criterion": "Falsifiability", "status": "pass", "reason": "Refutable by E4."},
                {"criterion": "Alternative explanations", "status": "fail", "reason": "Unresolved."},
            ],
            "issues": issues,
            "missing_information": [
                {"item": "Per-seed accuracy for the 3 runs of E4", "why_needed": "To bound variance."}
            ],
        }
    )


def setup_paper(client) -> int:
    branch = client.post("/api/branches", json={"name": "Urban heat"}).json()
    paper = client.post(f"/api/branches/{branch['id']}/papers", json={"title": "Humidity readings"}).json()
    return paper["id"]


def test_save_does_not_call_the_model(client, scripted):
    """`Save` must never trigger an LLM call. Only `Save & Analyze` does."""
    provider = scripted([])
    paper_id = setup_paper(client)

    response = client.post(
        f"/api/papers/{paper_id}/inputs", json={"label": "Day 1", "content": "An idea."}
    )
    assert response.status_code == 201
    assert provider.calls == []
    assert client.get("/api/usage/summary").json()["calls"] == 0


def test_checklist_starts_empty_with_eleven_sections(client):
    paper_id = setup_paper(client)
    readiness = client.get(f"/api/papers/{paper_id}/readiness").json()
    assert [s["key"] for s in readiness["sections"]] == list(SECTION_KEYS)
    assert all(s["status"] == "missing" for s in readiness["sections"])
    assert readiness["gate"]["can_compile"] is False


def test_full_workflow(client, scripted):
    paper_id = setup_paper(client)
    client.post(
        f"/api/papers/{paper_id}/inputs",
        json={"label": "E4", "content": "Model with humidity 2.1 C MAE vs baseline 2.9 C."},
    )

    # --- Extract + review the hypothesis section -------------------------
    scripted([extraction_json("H1", "humidity readings improve heat prediction"),
              review_json("needs_attention")])
    detail = client.post(f"/api/papers/{paper_id}/sections/hypothesis/recheck").json()

    assert detail["status"] == "needs_attention"
    assert detail["items"][0]["label"] == "H1"
    assert detail["items"][0]["provenance"] == "extracted"
    assert detail["items"][0]["source_input_ids"] == [1]
    assert len(detail["checks"]) == 2
    assert detail["issues"][0]["severity"] == "major"
    assert detail["missing_information"][0]["item"].startswith("Per-seed accuracy")

    # Give methodology real content so we can watch it become stale.
    scripted([extraction_json("M1", "the evaluation protocol"), review_json("ready", severity=None)])
    assert client.post(f"/api/papers/{paper_id}/sections/methodology/recheck").json()["status"] == "ready"

    # --- The researcher corrects the model's understanding ---------------
    item_id = detail["items"][0]["id"]
    edited = client.patch(
        f"/api/items/{item_id}", json={"statement": "Only for dense sensor coverage."}
    ).json()
    assert edited["confirmation"] == "edited"

    # Correcting the hypothesis invalidates the methodology that depends on it:
    # a READY section returns to NEEDS ATTENTION when its basis moves.
    readiness = client.get(f"/api/papers/{paper_id}/readiness").json()
    by_key = {s["key"]: s for s in readiness["sections"]}
    assert by_key["methodology"]["needs_recheck"] is True
    assert by_key["methodology"]["status"] == "needs_attention"

    # --- Re-check: the correction survives re-extraction ------------------
    scripted([extraction_json("H1", "AI would overwrite this"), review_json("ready", severity=None)])
    rechecked = client.post(f"/api/papers/{paper_id}/sections/hypothesis/recheck").json()
    assert rechecked["items"][0]["statement"] == "Only for dense sensor coverage."
    assert rechecked["status"] == "ready"
    assert rechecked["issues"] == []


def test_blocker_forces_needs_attention_even_if_model_says_ready(client, scripted):
    """A section with an open blocker is never READY, whatever the model reports."""
    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "x", "content": "content"})

    scripted([extraction_json("E1", "an experiment"), review_json("ready", severity="blocker")])
    detail = client.post(f"/api/papers/{paper_id}/sections/experiments/recheck").json()
    assert detail["status"] == "needs_attention"


def test_challenge_demotes_ready_sections_and_locks_compile(client, scripted):
    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "x", "content": "content"})

    scripted([extraction_json("H1", "hypothesis"), review_json("ready", severity=None)])
    assert client.post(f"/api/papers/{paper_id}/sections/hypothesis/recheck").json()["status"] == "ready"

    scripted(
        [
            json.dumps(
                {
                    "overall_assessment": "The central claim is not supported by E4.",
                    "issues": [
                        {
                            "severity": "blocker",
                            "issue": "Claim attributes the improvement to the humidity readings.",
                            "why_it_matters": "E4 cannot isolate the mechanism.",
                            "evidence": "E4 varies two factors.",
                            "recommended_action": "Run a matched-size control.",
                            "affected_sections": ["hypothesis", "experiments", "contribution"],
                        }
                    ],
                    "cross_section_observations": ["Scope widens between H1 and the abstract."],
                }
            )
        ]
    )
    result = client.post(f"/api/papers/{paper_id}/challenge").json()
    assert result["issues"][0]["severity"] == "blocker"
    assert "hypothesis" in result["issues"][0]["affected_sections"]

    # A cross-section blocker pulls the affected READY section back.
    detail = client.get(f"/api/papers/{paper_id}/sections/hypothesis").json()
    assert detail["status"] == "needs_attention"

    gate = client.get(f"/api/papers/{paper_id}/manuscript/gate").json()
    assert gate["can_compile"] is False
    assert gate["open_blockers"] == 1


def test_compile_is_locked_until_ready(client, scripted):
    paper_id = setup_paper(client)
    scripted([])
    response = client.post(f"/api/papers/{paper_id}/manuscript")
    assert response.status_code == 409
    assert "locked" in json.dumps(response.json()).lower()


def test_compile_unlocks_when_all_sections_ready(client, scripted, db):
    from peerlens.models import SectionState

    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "x", "content": "content"})
    for state in db.query(SectionState).filter(SectionState.paper_id == paper_id):
        state.status = "ready"
    db.commit()

    gate = client.get(f"/api/papers/{paper_id}/manuscript/gate").json()
    assert gate["can_compile"] is True

    scripted(
        [
            json.dumps(
                {
                    "title": "Street-level humidity for urban heat prediction",
                    "sections": [
                        {"heading": "Abstract", "markdown": "We study humidity readings."},
                        {"heading": "Results", "markdown": "2.1 C vs 2.9 C, single run."},
                    ],
                    "content_gaps": ["No variance reported for E4."],
                }
            )
        ]
    )
    manuscript = client.post(f"/api/papers/{paper_id}/manuscript").json()
    assert "Street-level humidity" in manuscript["title"]
    assert "2.1 C" in manuscript["markdown"]
    # Content gaps are surfaced, not silently filled.
    assert "No variance reported" in manuscript["markdown"]

    download = client.get(f"/api/manuscripts/{manuscript['id']}/markdown")
    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]


def test_dismissed_issues_are_not_resurrected(client, scripted):
    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "x", "content": "content"})

    scripted([extraction_json("E1", "an experiment"), review_json("needs_attention")])
    detail = client.post(f"/api/papers/{paper_id}/sections/experiments/recheck").json()
    issue_id = detail["issues"][0]["id"]
    client.patch(f"/api/issues/{issue_id}", json={"status": "dismissed"})

    scripted([extraction_json("E1", "an experiment"), review_json("needs_attention")])
    detail = client.post(f"/api/papers/{paper_id}/sections/experiments/recheck").json()
    assert detail["issues"] == []


def test_rejecting_an_item_keeps_it_out(client, scripted):
    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "x", "content": "content"})

    scripted([extraction_json("F1", "an unsupported finding"), review_json("incomplete")])
    detail = client.post(f"/api/papers/{paper_id}/sections/findings/recheck").json()
    client.post(f"/api/items/{detail['items'][0]['id']}/reject")

    scripted([extraction_json("F1", "an unsupported finding"), review_json("incomplete")])
    detail = client.post(f"/api/papers/{paper_id}/sections/findings/recheck").json()
    assert detail["items"] == []


def test_researcher_authored_items_are_marked_provided(client):
    paper_id = setup_paper(client)
    item = client.post(
        f"/api/papers/{paper_id}/items",
        json={"section_key": "limitations", "statement": "Only two datasets tested."},
    ).json()
    assert item["provenance"] == "provided"
    assert item["confirmation"] == "confirmed"


def test_new_input_marks_analyzed_sections_stale(client, scripted):
    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "first", "content": "content"})
    scripted([extraction_json("H1", "hypothesis"), review_json("ready", severity=None)])
    client.post(f"/api/papers/{paper_id}/sections/hypothesis/recheck")

    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "later", "content": "new results"})
    detail = client.get(f"/api/papers/{paper_id}/sections/hypothesis").json()
    assert detail["needs_recheck"] is True
    assert "New research material" in detail["recheck_reason"]


def test_usage_is_recorded_for_every_call(client, scripted):
    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "x", "content": "content"})
    scripted([extraction_json("H1", "hypothesis"), review_json("incomplete")])
    client.post(f"/api/papers/{paper_id}/sections/hypothesis/recheck")

    usage = client.get("/api/usage").json()
    assert usage["totals"]["calls"] == 2
    assert usage["totals"]["input_tokens"] == 200
    operations = {row["key"] for row in usage["by_operation"]}
    assert operations == {"extract:hypothesis", "review:hypothesis"}
    # Locally hosted models have no per-token billing.
    assert usage["totals"]["estimated_cost"] == 0.0


def test_analysis_without_provider_returns_a_clear_error(client):
    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "x", "content": "content"})
    response = client.post(f"/api/papers/{paper_id}/analyze")
    assert response.status_code == 400
    assert "Settings" in response.json()["detail"]


def test_research_data_survives_a_restart(client):
    """Restarting must not lose research: everything lives in SQLite on disk."""
    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "keep me", "content": "durable"})

    from fastapi.testclient import TestClient

    from peerlens.main import app

    with TestClient(app) as restarted:
        inputs = restarted.get(f"/api/papers/{paper_id}/inputs").json()
        assert [i["label"] for i in inputs] == ["keep me"]


def test_challenge_maps_aliased_section_names(client, scripted):
    """A blocker reported against "claims" must still reach Claims & Contribution."""
    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "x", "content": "content"})

    scripted([extraction_json("C1", "a claim"), review_json("ready", severity=None)])
    client.post(f"/api/papers/{paper_id}/sections/contribution/recheck")

    scripted(
        [
            json.dumps(
                {
                    "overall_assessment": "The claim exceeds the evidence.",
                    "issues": [
                        {
                            "severity": "blocker",
                            "issue": "Claim is unsupported.",
                            "why_it_matters": "The chain breaks at the result.",
                            "evidence": "No result supports C1.",
                            "recommended_action": "Narrow the claim.",
                            "affected_sections": ["claims", "state_of_the_art", "appendix"],
                        }
                    ],
                    "cross_section_observations": [],
                }
            )
        ]
    )
    result = client.post(f"/api/papers/{paper_id}/challenge").json()
    # "claims" -> contribution, "state_of_the_art" -> literature, "appendix" dropped.
    assert result["issues"][0]["affected_sections"] == ["literature", "contribution"]

    detail = client.get(f"/api/papers/{paper_id}/sections/contribution").json()
    assert detail["status"] == "needs_attention"
