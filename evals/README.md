# PeerLens Evaluations

Prompt quality is the product. These evaluations exist to answer one question:

> Does PeerLens actually detect the scientific defects it claims to detect?

Each case supplies deliberately flawed research material and asserts that the
relevant prompt surfaces the flaw at an appropriate severity — and that it does
not produce the specific wrong answers we care about (accepting a novelty claim
based on an unsuccessful search, inventing statistics, praising the work).

## Running

Evals call a real model, so they need a configured provider. Configure one in
Settings first, or pass the settings on the command line:

```bash
# Uses whatever provider is configured in the PeerLens database
python evals/run_evals.py

# Or target a provider explicitly
python evals/run_evals.py --provider ollama --model qwen3:8b
python evals/run_evals.py --provider anthropic --model claude-sonnet-4-5-20250929

# A single case, with the full model output printed
python evals/run_evals.py --case confounded_experiment --verbose
```

The structural test (`test_eval_cases.py`) validates every case file and runs in
CI without a model or an API key.

## Adding a case

Drop a JSON file into `evals/cases/`. No code changes are needed.

```jsonc
{
  "id": "unique_snake_case_id",
  "description": "What defect this case tests for.",
  "target": {"kind": "section_review", "section": "contribution"},
  "inputs": [{"label": "Draft", "content": "…the flawed research material…"}],
  "expect": {
    "min_severity": "major",          // the worst issue must be at least this bad
    "signals": [                       // each signal: any one regex must match
      {
        "name": "identifies the single-dataset basis",
        "any": ["single dataset", "one dataset", "one city"]
      }
    ],
    "forbidden": [                     // must NOT appear anywhere in the output
      {"name": "accepts novelty from absent search", "any": ["no prior work exists"]}
    ]
  }
}
```

`target.kind` is either `section_review` (with a `section` key) or `challenge`.

Signals are matched case-insensitively against the concatenated text of the
issues, checks and missing-information the model produced. Matching on wording
is a blunt instrument — it verifies that the right *concept* was raised, not
that the reasoning was good. Read the output with `--verbose` when a case is
close to the line; the score is a guide, not a verdict.
