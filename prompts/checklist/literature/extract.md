# EXTRACT — State of the Art

Extract what the supplied material says about existing work.

**Critical constraint:** you may only extract prior work that appears in the
supplied research material or the supplied literature list. You must not add
papers from your own memory, and you must not reconstruct citations. If you
recognise that relevant work exists but it was not supplied, put that in `notes`
as an unverified observation — never as an extracted item with a citation.

## What to extract

One item per distinct piece of prior work or per coherent line of work.

Useful `details` keys:

- `citation` — exactly as given in the material; never reformatted into a
  citation you cannot verify
- `year` — only if supplied
- `approach` — what that work does
- `relation` — one of `closest_prior_work`, `competing_approach`,
  `baseline`, `foundational`, `contradictory_evidence`, `background`
- `reported_outcome` — what the material says that work achieved
- `limitation` — the limitation the material attributes to it
- `verification` — `supplied_source` if it came from an uploaded paper or the
  literature list, `mentioned_only` if the researcher merely referred to it

## Guidance

- Distinguish the *closest* prior work from general background. The closest
  work is what determines whether the gap and the contribution survive review.
- Extract contradictory evidence with the same care as supporting evidence.
  Research material tends to under-report work that disagrees with it.
- Extract baselines the material treats as standard in this field, even when
  the researcher has not used them.
- Where the material characterises prior work ("X fails on sparse measurements"),
  record it, and record in `details.characterisation_basis` whether that came
  from reading the paper, from another paper's claim, or from assumption.
- Add a `notes` entry if the literature coverage looks narrow relative to the
  problem, but do not name specific missing papers you cannot verify.
