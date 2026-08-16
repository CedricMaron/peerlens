# EXTRACT — Research Gap

Extract what the material identifies as unresolved by existing work.

A gap is a specific, defensible statement of what prior work leaves open. It is
not "no one has done X", and it is not a description of the researcher's method.

## What to extract

Useful `details` keys:

- `unresolved` — precisely what remains unresolved
- `follows_from` — which prior work items (by label, e.g. `L2`) establish it
- `closest_work` — the nearest prior work, and what it does address
- `why_it_matters` — the scientific consequence of the gap
- `gap_type` — `empirical` (untested condition), `methodological` (no adequate
  method), `theoretical` (no explanation), `evidential` (conflicting results),
  or `coverage` (unstudied population/setting)
- `basis` — `supported_by_supplied_literature`, `asserted_by_researcher`, or
  `inferred_from_absence`

## Guidance

- Mark `basis` honestly. A gap justified only by the researcher not having found
  prior work is `inferred_from_absence`, and that distinction matters enormously
  for the review step.
- If the material states the gap only implicitly (via the method's motivation),
  extract it as `inferred` and say so.
- Link the gap to the literature items it derives from using relations of type
  `addresses`, and note where no such link exists in the material.
- Do not strengthen a vague gap into a sharp one. Extract the vagueness.
