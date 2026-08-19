#!/usr/bin/env python3
"""Run the PeerLens scientific evaluation cases against a real model.

    python evals/run_evals.py
    python evals/run_evals.py --provider ollama --model qwen3:8b
    python evals/run_evals.py --case confounded_experiment --verbose

Each case supplies deliberately flawed research and asserts that the relevant
prompt surfaces the flaw. The purpose is to improve scientific prompt quality
over time, so a failure is information, not a build break.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

CASES_DIR = Path(__file__).parent / "cases"
SEVERITY_RANK = {"note": 0, "minor": 1, "major": 2, "blocker": 3}


@dataclass
class CaseResult:
    case_id: str
    matched: list[str] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)
    violated: list[str] = field(default_factory=list)
    severity_ok: bool = True
    worst_severity: str = "none"
    error: str = ""
    raw: dict | None = None

    @property
    def passed(self) -> bool:
        return not self.error and not self.missed and not self.violated and self.severity_ok

    @property
    def score(self) -> str:
        total = len(self.matched) + len(self.missed)
        return f"{len(self.matched)}/{total}"


def load_cases(only: str | None = None) -> list[dict]:
    cases = []
    for path in sorted(CASES_DIR.glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        if only is None or case["id"] == only:
            cases.append(case)
    return cases


def searchable_text(payload: dict) -> str:
    """Everything the model said, flattened for concept matching."""
    parts: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            parts.append(node)

    walk(payload)
    return " ".join(parts).lower()


def worst_severity(issues: list[dict]) -> str:
    best = "none"
    for issue in issues:
        severity = str(issue.get("severity", "")).lower()
        if severity in SEVERITY_RANK and (
            best == "none" or SEVERITY_RANK[severity] > SEVERITY_RANK[best]
        ):
            best = severity
    return best


def grade(case: dict, payload: dict) -> CaseResult:
    result = CaseResult(case_id=case["id"], raw=payload)
    text = searchable_text(payload)
    expect = case.get("expect", {})

    for signal in expect.get("signals", []):
        if any(re.search(re.escape(p.lower()), text) for p in signal["any"]):
            result.matched.append(signal["name"])
        else:
            result.missed.append(signal["name"])

    for forbidden in expect.get("forbidden", []):
        if any(re.search(re.escape(p.lower()), text) for p in forbidden["any"]):
            result.violated.append(forbidden["name"])

    result.worst_severity = worst_severity(payload.get("issues", []) or [])
    required = expect.get("min_severity")
    if required:
        result.severity_ok = SEVERITY_RANK.get(result.worst_severity, -1) >= SEVERITY_RANK[required]
    return result


async def run_case(case: dict, db) -> CaseResult:
    """Build a throwaway paper containing the case material, then analyse it."""
    from peerlens.ai_schemas import ChallengeResult, ReviewResult
    from peerlens.models import PaperProject, ResearchBranch, ResearchInput
    from peerlens.services import analysis, research_state

    branch = ResearchBranch(name=f"eval:{case['id']}")
    db.add(branch)
    db.commit()
    paper = PaperProject(branch_id=branch.id, title=case["description"][:200])
    db.add(paper)
    db.commit()
    for entry in case["inputs"]:
        db.add(
            ResearchInput(
                paper_id=paper.id,
                label=entry.get("label", "material"),
                kind="text",
                content=entry["content"],
            )
        )
    db.commit()
    research_state.ensure_sections(db, paper.id)

    target = case["target"]
    try:
        if target["kind"] == "challenge":
            # Challenge reads the Research State, so populate it first.
            for key in ("hypothesis", "experiments", "results", "findings", "contribution"):
                try:
                    await analysis.extract_section(db, paper, key)
                except Exception:  # noqa: BLE001 - a thin section must not abort the case
                    pass
            result: ChallengeResult = await analysis.challenge_research(db, paper)
        else:
            section = target["section"]
            await analysis.extract_section(db, paper, section)
            result: ReviewResult = await analysis.review_section(db, paper, section)
    except Exception as exc:  # noqa: BLE001 - reported as a case error
        return CaseResult(case_id=case["id"], error=f"{type(exc).__name__}: {exc}")

    return grade(case, result.model_dump())


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run PeerLens scientific evals.")
    parser.add_argument(
        "--provider",
        choices=["claude-code", "codex", "anthropic", "openai", "ollama"],
    )
    parser.add_argument("--model")
    parser.add_argument("--api-key")
    parser.add_argument("--base-url")
    parser.add_argument("--case", help="Run a single case by id.")
    parser.add_argument("--verbose", action="store_true", help="Print full model output.")
    parser.add_argument(
        "--data-dir",
        help="Scratch data directory (default: a temporary one, leaving your database alone).",
    )
    args = parser.parse_args()

    import os

    data_dir = args.data_dir or tempfile.mkdtemp(prefix="peerlens-evals-")
    if not args.data_dir:
        # Use a throwaway database unless the user asked for their own.
        os.environ["PEERLENS_DATA_DIR"] = data_dir
        os.environ["PEERLENS_DATABASE_URL"] = f"sqlite:///{Path(data_dir) / 'evals.db'}"

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from peerlens.db import SessionLocal, init_db
    from peerlens.services import settings_service

    init_db()
    db = SessionLocal()

    if args.provider:
        settings_service.save_provider_config(
            db, args.provider, args.model or "", args.api_key, args.base_url
        )
    config = settings_service.get_provider_config(db)
    if config is None:
        print(
            "No AI provider configured. Configure one in Settings, or pass "
            "--provider/--model on the command line.",
            file=sys.stderr,
        )
        return 2

    cases = load_cases(args.case)
    if not cases:
        print(f"No cases found{f' matching {args.case}' if args.case else ''}.", file=sys.stderr)
        return 2

    print(f"PeerLens evals — {config.provider}/{config.model} — {len(cases)} case(s)\n")

    results: list[CaseResult] = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']} … ", end="", flush=True)
        result = await run_case(case, db)
        results.append(result)
        if result.error:
            print(f"ERROR — {result.error}")
        else:
            mark = "PASS" if result.passed else "FAIL"
            print(f"{mark}  signals {result.score}  worst severity: {result.worst_severity}")
        for name in result.missed:
            print(f"        missed signal: {name}")
        for name in result.violated:
            print(f"        FORBIDDEN content present: {name}")
        if not result.severity_ok:
            required = case["expect"]["min_severity"]
            print(f"        severity too low: got {result.worst_severity}, expected >= {required}")
        if args.verbose and result.raw:
            print(json.dumps(result.raw, indent=2)[:6000])

    passed = sum(1 for r in results if r.passed)
    signals_hit = sum(len(r.matched) for r in results)
    signals_total = sum(len(r.matched) + len(r.missed) for r in results)
    print(f"\n{passed}/{len(results)} cases passed · {signals_hit}/{signals_total} signals detected")
    if passed < len(results):
        print("A failing case is a prompt-quality signal, not necessarily a defect in the code.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
