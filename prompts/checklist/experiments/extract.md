# EXTRACT — Experiments

Extract each concrete experiment the research runs.

## What to extract

One item per experiment (`E1`, `E2`, ...), reusing the researcher's own labels.

Useful `details` keys:

- `purpose` — what this experiment is meant to establish
- `tests_hypothesis` — which hypothesis label(s) it tests
- `manipulated` — what is varied between conditions
- `held_constant` — what is controlled
- `conditions` — the arms/conditions compared
- `baselines` — comparators included
- `dataset` — data used
- `metrics` — what is measured
- `repetitions` — seeds, runs, folds
- `is_ablation` — `true` when it isolates a component

## Guidance

- For each experiment, record precisely what differs between conditions. If more
  than one thing differs, record all of them — this is exactly the information
  the review step needs to detect confounding, and it is routinely glossed over
  in research notes.
- Link experiments to hypotheses with `tested_by` relations (hypothesis is the
  source, experiment the target), and to results with `produces` relations.
- If an experiment appears in the material with no stated purpose, extract it
  with `purpose` marked as not stated, rather than inferring a flattering one.
- Extract planned-but-not-run experiments too, marking `status` in details as
  `planned`. Do not present planned work as completed.
