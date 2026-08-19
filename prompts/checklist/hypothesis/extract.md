# EXTRACT — Hypothesis

Extract the falsifiable predictions the research makes.

## What to extract

One item per hypothesis (`H1`, `H2`, ...), using the researcher's own numbering
if they have one.

Useful `details` keys:

- `scope` — the conditions under which the hypothesis is claimed to hold
  (e.g. "one city, summer months only")
- `independent_variable` — what is manipulated
- `dependent_variable` — what is measured
- `expected_effect` — the predicted direction and, if stated, magnitude
- `mechanism` — the causal story the researcher proposes, if any
- `assumptions` — what must hold for the prediction to follow
- `would_be_refuted_by` — the observation that would count against it, if the
  material states one
- `status` — `stated`, `implied_by_method`, or `implied_by_claims`

## Guidance

- Many researchers never write hypotheses down explicitly. If the hypothesis is
  implicit in the method or the claims, extract it and mark it `inferred`, with
  `status` recording where you recovered it from. This is useful precisely
  because it makes an unexamined assumption visible.
- Keep the researcher's predicted mechanism separate from the predicted effect.
  Conflating "the added readings improve accuracy" (effect) with "because they
  capture local humidity variation" (mechanism) hides the fact that the
  mechanism usually goes untested.
- Do not repair an unfalsifiable hypothesis into a falsifiable one. Extract it
  as stated; the review step handles it.
- Link each hypothesis to the experiments that test it with `tested_by`
  relations, where the material makes that connection.
