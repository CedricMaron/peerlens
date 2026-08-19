# EXTRACT — Results

Extract raw observations. A result is what was measured, not what it means.

## What to extract

One item per distinct observation (`R1`, `R2`, ...).

Useful `details` keys:

- `from_experiment` — the experiment label that produced it
- `condition` — the specific condition/arm
- `metric` — what was measured
- `value` — the measured value, exactly as supplied
- `uncertainty` — standard deviation, confidence interval, range, or number of
  runs, if supplied
- `comparison` — the value it is compared against, if any
- `direction` — `positive`, `negative`, `null`, or `mixed` relative to the
  hypothesis
- `statistical_test` — the test and its output, only if actually supplied

## Guidance

- **Transcribe numbers exactly.** Never round, rescale, recompute, aggregate or
  "clean up" a value. If a CSV or table was supplied, read from it directly.
- **Do not interpret.** "Error fell from 2.9 C to 2.1 C" is a result.
  "The method improves accuracy" is a finding and belongs to the next section.
- **Extract negative, null and mixed results with equal prominence.** These are
  the results most likely to be dropped between notes and manuscript, and
  preserving them is a core function of PeerLens. Set `direction` honestly.
- If uncertainty is not reported, leave `uncertainty` absent rather than
  implying a single run is a point estimate with unknown variance — and note the
  omission in `notes`.
- If a result is described qualitatively ("performed better"), extract it as
  qualitative and record that no numeric value was supplied.
- Never compute a statistical test yourself, and never describe a difference as
  significant unless the material supplies the test result.
