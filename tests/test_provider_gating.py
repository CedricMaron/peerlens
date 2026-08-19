"""The separation the provider layer must never break.

A provider executes an AI request. PeerLens decides whether a section is READY
and whether the manuscript may be compiled. These tests pin that boundary: no
model output, and no provider switch, can move the gate.
"""

from __future__ import annotations

import json

from peerlens.models import SectionState
from peerlens.sections import REQUIRED_SECTION_KEYS, SECTION_KEYS
from peerlens.services import settings_service
from tests.test_workflow import extraction_json, review_json, setup_paper


def set_ready(db, paper_id: int, keys) -> None:
    for state in db.query(SectionState).filter(SectionState.paper_id == paper_id):
        state.status = "ready" if state.key in keys else "missing"
    db.commit()


def test_eleven_required_sections_exist_whatever_the_provider(client, db):
    settings_service.select_provider(db, "claude-code")
    paper_id = setup_paper(client)
    readiness = client.get(f"/api/papers/{paper_id}/readiness").json()

    assert len(SECTION_KEYS) == 11
    assert len(REQUIRED_SECTION_KEYS) == 11
    assert [s["key"] for s in readiness["sections"]] == list(SECTION_KEYS)
    assert readiness["gate"]["required_sections"] == 11
    assert readiness["gate"]["ready_sections"] == 0
    assert readiness["gate"]["can_compile"] is False


def test_compile_stays_locked_at_ten_of_eleven(client, db, scripted):
    provider = scripted([])
    paper_id = setup_paper(client)
    set_ready(db, paper_id, list(REQUIRED_SECTION_KEYS[:10]))

    gate = client.get(f"/api/papers/{paper_id}/manuscript/gate").json()
    assert gate["ready_sections"] == 10
    assert gate["can_compile"] is False
    assert "Limitations" in " ".join(gate["reasons"])

    response = client.post(f"/api/papers/{paper_id}/manuscript")
    assert response.status_code == 409
    # The gate is checked before any AI request: no provider was involved.
    assert provider.calls == []


def test_compile_unlocks_at_exactly_eleven(client, db, scripted):
    paper_id = setup_paper(client)
    set_ready(db, paper_id, list(REQUIRED_SECTION_KEYS))

    gate = client.get(f"/api/papers/{paper_id}/manuscript/gate").json()
    assert (gate["ready_sections"], gate["can_compile"]) == (11, True)

    scripted(
        [
            json.dumps(
                {
                    "title": "A defensible study",
                    "sections": [{"heading": "Abstract", "markdown": "We report X."}],
                    "content_gaps": [],
                }
            )
        ]
    )
    manuscript = client.post(f"/api/papers/{paper_id}/manuscript").json()
    assert manuscript["title"] == "A defensible study"
    # Reproducibility: the manuscript records which provider produced it.
    generation = manuscript["sections"]["generation"]
    assert generation["provider"] == "scripted"
    assert generation["task_type"] == "compile_manuscript"
    assert generation["usage"]["input_tokens"] == 100


def test_a_provider_claiming_everything_is_ready_cannot_unlock_compile(client, scripted):
    """Readiness comes from PeerLens's own evaluation, not from model prose."""
    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "x", "content": "one idea"})

    # The model asserts READY for one section while raising a blocker, and
    # claims in prose that the whole paper is finished.
    scripted(
        [
            extraction_json("H1", "a hypothesis"),
            json.dumps(
                {
                    "status": "ready",
                    "summary": "All eleven sections are READY. The manuscript can be compiled.",
                    "checks": [],
                    "issues": [
                        {
                            "severity": "blocker",
                            "issue": "The hypothesis is not falsifiable.",
                            "why_it_matters": "No observation could refute it.",
                            "evidence": "input #1",
                            "recommended_action": "State a refutation criterion.",
                            "affected_sections": ["hypothesis"],
                        }
                    ],
                    "missing_information": [],
                }
            ),
        ]
    )
    detail = client.post(f"/api/papers/{paper_id}/sections/hypothesis/recheck").json()
    assert detail["status"] == "needs_attention"  # a blocker outranks the model's verdict

    gate = client.get(f"/api/papers/{paper_id}/manuscript/gate").json()
    assert gate["can_compile"] is False
    assert gate["ready_sections"] == 0
    assert client.post(f"/api/papers/{paper_id}/manuscript").status_code == 409


def test_switching_providers_preserves_readiness_and_history(client, db, scripted):
    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "x", "content": "content"})

    settings_service.save_provider_config(db, "openai", "gpt-4.1", "sk-x", None)
    scripted([extraction_json("M1", "the evaluation protocol"), review_json("ready", severity=None)])
    client.post(f"/api/papers/{paper_id}/sections/methodology/recheck")

    before = client.get(f"/api/papers/{paper_id}/readiness").json()
    usage_before = client.get("/api/usage").json()["totals"]["calls"]

    # Switch provider twice, including to an account-backed CLI provider.
    for provider_id in ("claude-code", "ollama", "openai"):
        assert client.post(f"/api/settings/providers/{provider_id}/select").status_code == 200

    after = client.get(f"/api/papers/{paper_id}/readiness").json()
    assert after["sections"] == before["sections"]
    assert after["gate"] == before["gate"]
    assert client.get(f"/api/papers/{paper_id}/sections/methodology").json()["status"] == "ready"
    # Usage history is not erased by switching providers either.
    assert client.get("/api/usage").json()["totals"]["calls"] == usage_before


def test_challenge_is_available_before_eleven_of_eleven(client, scripted):
    """Challenge My Research is a separate action, not a reward for being READY."""
    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "x", "content": "content"})

    scripted(
        [
            json.dumps(
                {
                    "overall_assessment": "The evidence chain breaks at the result.",
                    "issues": [
                        {
                            "severity": "major",
                            "issue": "No baseline was run.",
                            "why_it_matters": "The improvement cannot be located.",
                            "evidence": "No baseline appears in the material.",
                            "recommended_action": "Run the missing baseline.",
                            "affected_sections": ["experiments"],
                        }
                    ],
                    "cross_section_observations": [],
                }
            )
        ]
    )
    result = client.post(f"/api/papers/{paper_id}/challenge").json()
    assert result["issues"][0]["severity"] == "major"
    # Provider provenance travels with the result.
    assert result["meta"]["provider"] == "scripted"
    assert result["meta"]["task_type"] == "challenge_research"
    assert client.get(f"/api/papers/{paper_id}/manuscript/gate").json()["can_compile"] is False


def test_unknown_provider_is_rejected_by_the_api(client):
    assert client.post("/api/settings/providers/not-a-provider/select").status_code == 404
    assert client.post("/api/settings/providers/not-a-provider/login").status_code == 404
    response = client.put(
        "/api/settings/provider", json={"provider": "not-a-provider", "model": "x"}
    )
    assert response.status_code == 404


def test_api_providers_still_require_a_model(client):
    response = client.put("/api/settings/provider", json={"provider": "openai", "model": ""})
    assert response.status_code == 422


def test_login_is_only_offered_where_a_cli_owns_it(client):
    assert client.post("/api/settings/providers/openai/login").status_code == 400
    assert client.post("/api/settings/providers/ollama/login").status_code == 400


def test_provider_catalogue_lists_every_option(client):
    data = client.get("/api/settings/providers").json()
    assert [p["id"] for p in data["providers"]] == [
        "claude-code",
        "codex",
        "anthropic",
        "openai",
        "ollama",
    ]
    by_id = {p["id"]: p for p in data["providers"]}
    assert by_id["claude-code"]["supports_login"] is True
    assert by_id["openai"]["needs_api_key"] is True
    assert by_id["ollama"]["is_local"] is True
    # Nothing in the catalogue exposes a stored secret.
    assert "sk-" not in json.dumps(data).replace("sk-…", "")


def test_analysis_records_provider_metadata(client, scripted):
    paper_id = setup_paper(client)
    client.post(f"/api/papers/{paper_id}/inputs", json={"label": "x", "content": "content"})
    scripted([extraction_json("H1", "a hypothesis"), review_json("incomplete")] * 11)

    result = client.post(
        f"/api/papers/{paper_id}/analyze", json={"sections": ["hypothesis"], "run_review": True}
    ).json()
    assert result["meta"]["provider"] == "scripted"
    assert result["meta"]["duration_ms"] is not None
    assert result["readiness"]["gate"]["required_sections"] == 11
