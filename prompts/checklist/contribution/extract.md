# EXTRACT — Claims & Contribution

Extract the broader scientific statements the research makes, and the knowledge
it claims to add.

Distinguish two item kinds and mark them in `details.kind`:

- `claim` — a scientific statement the paper asserts (`C1`, `C2`, ...)
- `contribution` — knowledge the work adds to the field (`CT1`, `CT2`, ...)

## What to extract

Useful `details` keys:

- `kind` — `claim` or `contribution`
- `supported_by` — finding labels supporting it
- `scope` — the conditions the claim is asserted over
- `strength` — the modality actually used: `universal` ("X improves Y"),
  `conditional` ("under Z, X improves Y"), or `hedged` ("X may improve Y")
- `contribution_type` — `empirical`, `methodological`, `theoretical`,
  `artifact`, `dataset`, or `engineering`
- `novelty_basis` — how novelty is justified: `compared_to_supplied_prior_work`,
  `asserted`, or `absence_of_found_work`

## Guidance

- Extract claims **as stated**, preserving their exact strength. If the material
  says "our method improves knowledge transfer", the claim is universal — do not
  soften it to "improves knowledge transfer in the tested setting". The gap
  between stated strength and evidenced strength is precisely what the review
  step must see.
- Look for claims in abstracts, conclusions, titles and slide notes, not just in
  a section labelled contributions. Claims made in an abstract count.
- Distinguish scientific contributions from engineering ones honestly. A faster
  implementation is a real contribution of type `engineering`; recording it as
  such is not a criticism.
- Link claims to supporting findings (`supports`) and to contributions
  (`contributes_to`).
