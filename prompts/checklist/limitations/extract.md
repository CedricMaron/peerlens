# EXTRACT — Limitations

Extract the real limits on what this research can conclude.

## What to extract

One item per limitation (`LIM1`, `LIM2`, ...).

Useful `details` keys:

- `limitation_type` — `assumption`, `scope_restriction`, `untested_condition`,
  `measurement_limitation`, `confound`, `external_validity`, or
  `unresolved_uncertainty`
- `affects` — which claims or findings (by label) it constrains
- `consequence` — what specifically cannot be concluded because of it
- `acknowledged` — `true` if the researcher states it, `false` if you derived it
  from the methodology, experiments or results

## Guidance

- Extract both the limitations the researcher states and the ones implied by the
  evidence. Mark derived ones `inferred` with `acknowledged: false` — these are
  usually the ones that matter.
- Tie every limitation to a specific claim or finding it constrains. A
  limitation that constrains nothing is decoration.
- Do not extract generic limitations. "Only evaluated on two datasets" is only a
  limitation if the claims extend beyond those two datasets — in which case
  state that connection.
- Assumptions that were never tested are limitations, even when the researcher
  regards them as obviously true.
