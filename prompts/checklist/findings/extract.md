# EXTRACT — Findings

Extract the interpretations the research draws from its results.

A finding is an interpretation *directly supported by results*. It sits between
a raw result and a broader claim.

## What to extract

One item per finding (`F1`, `F2`, ...).

Useful `details` keys:

- `supported_by` — the result labels (`R1`, `R3`) that support it
- `scope` — the conditions under which the finding holds, as evidenced
- `strength` — `direct` (restates what results show), `moderate` (requires an
  interpretive step), or `speculative` (goes well beyond the results)
- `alternative_explanations` — any the material itself acknowledges
- `direction` — whether it supports, contradicts, or is neutral toward the
  hypothesis

## Guidance

- Set `strength` by comparing the finding against the results actually supplied,
  not against how confidently it is written. Confident prose over a single
  observation is `speculative`.
- Link every finding to its supporting results with `supports` relations
  (result → finding). If a finding has no traceable supporting result, extract
  it with an empty `supported_by` — that emptiness is the point.
- Extract findings that contradict the hypothesis with the same care as
  confirming ones.
- Do not upgrade a result into a finding on the researcher's behalf, and do not
  merge several findings into a single tidier one.
