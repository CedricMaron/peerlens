# PeerLens

[![CI](https://github.com/CedricMaron/peerlens/actions/workflows/ci.yml/badge.svg)](https://github.com/CedricMaron/peerlens/actions/workflows/ci.yml)
[![Docker](https://github.com/CedricMaron/peerlens/actions/workflows/docker.yml/badge.svg)](https://github.com/CedricMaron/peerlens/actions/workflows/docker.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**AI-assisted scientific research quality control.**

Add ideas, literature, experiments and results as your research evolves.

PeerLens structures what it understands, reviews each scientific component,
shows what is missing or weak, and helps researchers make the work ready
before compiling it into a manuscript.

**Research quality first. Writing second.**

---

## The problem it solves

Most AI writing tools help you produce a manuscript faster. That is the wrong
end of the problem. A well-written paper built on a confounded experiment is
still a confounded experiment — the fluency just makes the defect harder to see.

The failures that get papers rejected, or worse, get them published and then
contradicted, are almost always structural:

- the central claim attributes an effect to a mechanism the experiment never isolated
- a universal claim rests on a single dataset
- "significant" appears without a statistical test
- an important baseline was never run
- novelty is claimed because a literature search returned nothing
- a negative result quietly disappeared between the notes and the abstract

PeerLens looks for exactly these. It does not try to make your writing better.
It tries to make your research **defensible**.

## How it works

You add whatever research material you have, whenever you have it — a
half-formed idea on day one, papers next week, a results CSV three months later.
Input stays deliberately free-form; there is no large scientific form to fill in.

```
FREE-FORM RESEARCH INPUT
        ↓
UNDERSTAND RESEARCH
        ↓
RESEARCH STATE
        ↓
RESEARCH CHECKLIST
        ↓
EXTRACT → SHOW → CHALLENGE → IMPROVE
        ↓
ALL REQUIRED SECTIONS READY
        ↓
COMPILE MANUSCRIPT
```

PeerLens progressively extracts what it understands into a structured **Research
State**, and tracks the eleven components of a defensible study in the
**Research Checklist**:

```
✓ 1. Problem              ◐ 7. Experiments
✓ 2. State of the Art     ○ 8. Results
◐ 3. Research Gap         ○ 9. Findings
✓ 4. Research Question    ○ 10. Claims & Contribution
⚠ 5. Hypothesis           ○ 11. Limitations
✓ 6. Methodology

○ MISSING   ◐ INCOMPLETE   ⚠ NEEDS ATTENTION   ✓ READY
```

**The checklist is the product.** Everything else exists to populate and defend it.

There are no invented scores. You will never see `82/100`, because that number
would mean nothing.

## Main features

**Specialized scientific review.** Every checklist section has its own two
prompts — one for extraction, one for review — written for that section's actual
scientific purpose. The hypothesis is reviewed for falsifiability and competing
explanations; experiments for discriminating power, controls and baselines;
claims for whether the evidence chain reaches a result. No generic prompt is
reused across sections.

**Challenge My Research.** A cross-section review that traces each headline
claim backwards — claim → finding → result → experiment → methodology — and
reports the exact link where it breaks. This is the feature that finds the
problems a section-by-section reading structurally cannot:

```
BLOCKER
The central claim attributes the improvement to the humidity readings.
However, E4 varies both the humidity readings and the number of stations.

Why it matters:
The experiment cannot isolate the claimed mechanism.

Affects: hypothesis, experiments, contribution

Recommended action:
Run a matched control with the same number of stations.
```

**Provenance you can inspect and correct.** Everything PeerLens believes is
labelled `PROVIDED`, `EXTRACTED`, `INFERRED` or `SUGGESTED`, and carries links
back to the research inputs it came from. You can **Confirm**, **Edit** or
**Reject** any of it. AI inference is never silently promoted into
researcher-confirmed fact, and your corrections are never overwritten by a later
re-analysis.

**Dependencies that propagate.** Research evolves. When new results arrive, the
sections that depended on them — findings, claims, contribution, limitations —
return to NEEDS ATTENTION. A section does not stay READY just because it was
READY yesterday.

**Compile Manuscript is locked** until every required section is READY and no
unresolved BLOCKERs remain. When it runs, it assembles the manuscript from
reviewed Research State: it will not invent results, citations or methodology,
will not strengthen a claim, and reports what was missing in a `content_gaps`
list rather than filling the hole with plausible prose.

**Literature.** OpenAlex search, DOI lookup, manual entry, PDF upload. PeerLens
is not a citation manager and does not try to be. It never fabricates a
reference, and it never concludes that no prior work exists because a search
returned nothing — the permitted phrasing is *"no equivalent work was identified
in the current search."*

**Usage tracking.** Every AI call records provider, model, operation, tokens,
latency and estimated cost. Values a provider does not report are stored and
shown as unknown — never estimated, never fabricated.

## Quick start (Docker — recommended)

```bash
docker run -p 8000:8000 -v peerlens-data:/app/data ghcr.io/cedricmaron/peerlens:latest
```

Then open <http://peerlens.localhost:8000> → **Settings** → connect an AI
provider → start your research.

That name needs no setup: browsers resolve any `*.localhost` address to your own
machine, and a real name is easier to find in a browser history full of
`localhost:` ports. Plain <http://localhost:8000> works exactly the same.

You do not need Python, Node.js, npm, a database server, Redis, or PostgreSQL.
One container, one port, one data location.

Your research lives in the `peerlens-data` volume and survives container
replacement and upgrades.

The container has no Claude Code or Codex CLI inside it, so those two providers
show as *not installed* there — use an API key or Ollama in Docker, or run
PeerLens natively (`./run.sh`) to use your Claude or ChatGPT account.

<details>
<summary>Docker Compose (optional convenience)</summary>

```bash
curl -O https://raw.githubusercontent.com/CedricMaron/peerlens/main/docker-compose.yml
docker compose up -d
```
</details>

## AI providers

Configure in **Settings → AI Provider**. No `.env` editing is required for
normal local use.

| Provider | Needs | Notes |
|---|---|---|
| **Claude Code** | the official CLI, signed in | Uses your existing Claude account. No API key. |
| **OpenAI Codex** | the official CLI, signed in | Uses your existing ChatGPT account. No API key. |
| **Anthropic API** | API key + model | |
| **OpenAI API** | API key + model | |
| **Ollama** | base URL + model | Fully local. No API key, no data leaves your machine. |

Settings shows what is installed, what is connected and what is configured, and
**Test Connection** runs a real round-trip before you commit to a provider.

### Setup

**Option A — Claude Code**

1. Install Claude Code and run `claude` once.
2. Sign in with the official Claude flow (`claude auth login`, or **Connect** in
   Settings, which runs the same command).
3. Start PeerLens → **Settings → AI Provider** → **Use Claude Code**.

**Option B — OpenAI Codex**

1. Install the Codex CLI (`npm install -g @openai/codex`).
2. Authenticate with `codex login`, or **Connect ChatGPT** in Settings.
3. Select **OpenAI Codex**.

**Option C — Anthropic API** — configure an Anthropic API key.

**Option D — OpenAI API** — configure an OpenAI API key.

**Option E — Ollama** — run a model locally and select **Ollama**.

For Claude Code and Codex the model field is optional: leave it blank to use
whatever the CLI is configured to use.

### What PeerLens does and does not do with your account

- **Claude/ChatGPT subscriptions and API billing are separate systems.** A Claude
  Pro subscription does not pay for Anthropic API calls, and vice versa.
- Account-backed access is **delegated entirely to the official Claude Code and
  Codex tooling**. PeerLens starts the official login command and watches the
  process; the browser flow belongs to the CLI.
- PeerLens **never asks for a Claude or ChatGPT password**, never reads or copies
  a credential file, never touches browser cookies, and never stores a session
  token.
- API keys are stored server-side in your local SQLite database. They are never
  sent to the browser (only a masked hint), never logged, and never written to
  browser storage.
- **Using Ollama keeps model inference on your machine.** Nothing is sent to a
  cloud provider.
- **There is no silent fallback.** If the selected provider fails, the request
  fails. PeerLens will not re-send unpublished research to a different vendor
  without you choosing it.

Claude Code and Codex are used as **inference backends**, not as coding agents.
Every tool is disabled (`--tools ""` / `--sandbox read-only`), customizations
(hooks, skills, plugins, MCP, `CLAUDE.md`) are switched off, and the working
directory is an empty scratch folder inside the data directory — a research
request cannot read or modify the PeerLens repository or anything else.

Because those two providers are billed through a subscription rather than
per token, the Usage page shows their cost as **unknown** rather than inventing
a per-token estimate. Token counts are recorded when the CLI reports them.

Windows users: if the CLI is installed inside WSL rather than on the Windows
host, PeerLens finds it there automatically.

### Using a local Ollama model

PeerLens works end to end with no cloud provider at all:

```bash
ollama pull qwen3:8b
ollama serve
```

Then in Settings choose **Ollama**, base URL `http://localhost:11434`, and pick
your model — installed models are detected automatically.

Running PeerLens in Docker and Ollama on the host? Use
`http://host.docker.internal:11434`.

> **Expectations for local models.** They are slower and less capable than
> frontier cloud models. On an 8B model running on CPU, expect several minutes
> per section review and considerably longer for manuscript compilation — the
> default timeout is 15 minutes for that reason, and you may need to raise
> `PEERLENS_LLM_TIMEOUT` further. Read their criticism more sceptically: smaller
> models are more prone to citing evidence that is not in your material, and may
> omit a requested manuscript section. Local models are genuinely useful for
> extraction and for a first pass; for the Challenge review and final
> compilation, a frontier model is meaningfully better.

## Native development setup

For contributors. Docker remains the recommended path for normal use.

**Linux / macOS**

```bash
./setup.sh   # checks versions, creates .venv, installs deps, initializes SQLite
./run.sh     # API on :8000, Vite dev server on :5173
```

**Windows PowerShell**

```powershell
.\setup.ps1
.\run.ps1
```

Windows blocks unsigned scripts by default. If you see *"running scripts is
disabled on this system"*, either run them explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

or allow local scripts once, for your user only:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
Unblock-File .\setup.ps1, .\run.ps1
```

Both setup scripts are safe to run repeatedly and install nothing globally.
Use `./run.sh --prod` (or `.\run.ps1 -Prod`) to build the frontend and serve
everything from port 8000, exactly as the container does.

Requirements: Python 3.11+, Node.js 20+.

If port 8000 is already in use, set `PEERLENS_PORT` (both scripts honour it, and
the Vite dev proxy follows it):

```bash
PEERLENS_PORT=8123 ./run.sh --prod    # http://peerlens.localhost:8123
```

Put it in `.env` to set it once. PeerLens has no authentication, so if other
machines can reach yours, also set `PEERLENS_HOST=127.0.0.1` to keep it on
loopback:

```
PEERLENS_HOST=127.0.0.1
PEERLENS_PORT=8123
```

## Architecture

Deliberately lightweight. One process, one database file, no message queues, no
vector database, no microservices, no multi-agent framework.

```
backend/peerlens/
  main.py            FastAPI app; serves the API and the compiled React app
  models.py          SQLAlchemy schema (SQLite)
  sections.py        The eleven checklist sections and their dependency graph
  ai_schemas.py      Pydantic schemas that every LLM response must validate against
  prompts_loader.py  Composes prompts from prompts/
  llm/               Provider layer + usage accounting
    manager.py         The provider registry (the only place providers are listed)
    base.py            AIRequest / AIEvent / provider interface
    providers.py       OpenAI, Anthropic and Ollama over HTTP
    cli_provider.py    Shared behaviour for CLI-backed providers
    claude_code.py     Claude Code (your Claude account, via the official CLI)
    codex_cli.py       OpenAI Codex (your ChatGPT account, via the official CLI)
    process.py         Subprocess control: fixed binaries, argv arrays, cancellation
    login.py           Supervises the official CLI login flows
    errors.py          Normalized provider error codes
  services/          Ingestion, research state, analysis, readiness, manuscript, literature
  routers/           HTTP API

prompts/
  shared/            Scientific rules included in every call
  checklist/<section>/{extract,review}.md    22 specialized prompts
  global/            challenge_research, compile_manuscript, literature_analysis

frontend/src/        React + Vite + TypeScript
evals/               Scientific evaluation cases
```

**Stack:** Python · FastAPI · SQLAlchemy · SQLite · Pydantic · httpx ·
React · Vite · TypeScript.

Scientific entities (hypotheses, experiments, results, findings, claims) and the
relationships between them (`tested_by`, `produces`, `supports`, `contradicts`,
`contributes_to`) are stored as ordinary rows in SQLite. No graph database is
needed at this scale.

Structured LLM output is validated with Pydantic, with one automatic repair
attempt before an error is surfaced. Malformed scientific output is never
silently accepted.

**Providers execute requests; PeerLens judges research.** A provider receives a
prompt and returns text, and that is the whole of its job. It cannot mark a
section READY, resolve an issue or unlock the manuscript:

```
research material -> context builder -> prompt -> selected provider
   -> structured output -> PeerLens parser -> readiness evaluation -> checklist
```

Adding a provider means adding one class and one registry entry in
`llm/manager.py`. Nothing in `services/` changes, which is exactly the point.

## Evaluations

Prompt quality is the asset, so it is tested.

```bash
python evals/run_evals.py                       # uses your configured provider
python evals/run_evals.py --provider ollama --model qwen3:8b
python evals/run_evals.py --case confounded_experiment --verbose
```

Ten cases cover the defect classes PeerLens claims to detect: universal claims
from one dataset, significance without statistics, confounded experiments,
missing baselines, novelty from an unsuccessful search, conclusions stronger
than the evidence, ignored negative results, methodology that cannot test its
hypothesis, findings unsupported by results, and contributions already covered
by supplied prior work.

Cases are plain JSON in `evals/cases/` — adding one requires no code changes.
See [evals/README.md](evals/README.md).

```bash
pytest tests/ evals/    # unit and integration tests; no API key needed
```

## Scientific limitations

Please read this section before trusting anything PeerLens tells you.

- **PeerLens does not replace scientific judgment or peer review.** It is a tool
  for catching structural problems earlier, not an authority on your field.
- It reasons **only over the material you supply**. It cannot know about the
  experiment you ran but did not write down.
- **Literature coverage is limited to what you add.** A clean literature review
  in PeerLens is not evidence of novelty. It never means "no prior work exists".
- **Language models are wrong sometimes**, including confidently. They can
  misread a method, miss a real defect, or raise one that is not there. Smaller
  local models are noticeably more prone to citing evidence that is not present
  in your material.
- It **cannot verify your data**. If a number is wrong in your CSV, it is wrong
  in the analysis.
- An empty issue list means nothing was detected in the supplied material — not
  that the research is sound.
- Treat everything it produces as a prompt for your own judgment, **especially
  when it agrees with you**.

## Project status

V1. The complete workflow works end to end: create a research branch and paper
projects, add free-form research and files, analyze, inspect and correct the
extracted understanding, run specialized section reviews, challenge the whole
research, and compile a manuscript once the checklist is READY.

Known limitations of this release:

- No OCR — scanned PDFs with no text layer are stored but not extracted.
- Analysis is synchronous; a full 11-section pass on a slow local model takes a
  while, and the UI waits on it.
- Single user. No authentication, collaboration or billing, by design.

## Contributing

Contributions are welcome, particularly to the prompts — that is where the
scientific quality lives.

1. Fork and branch from `main`.
2. `./setup.sh`, then `pytest tests/ evals/`.
3. **If you change a prompt, add or update an eval case** that demonstrates the
   improvement. A prompt change without an eval is hard to evaluate.
4. Keep the architecture boring. New infrastructure needs a concrete, present
   requirement — not an anticipated one.

Good first contributions: additional eval cases for defect classes not yet
covered, section prompt improvements, and better handling of tabular results.

## License

MIT — see [LICENSE](LICENSE).
