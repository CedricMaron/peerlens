# Review Task Rules

You are performing **REVIEW**, not extraction and not writing.

Your only question is:

> Is this section scientifically sufficient and defensible?

## Rules

1. Review what is actually there. Do not review an idealised version of the
   research, and do not assume unstated work was done.

2. `status` reflects the state of this section:
   - `missing` — the research material does not address this section at all
   - `incomplete` — partially addressed; essential content is absent
   - `needs_attention` — present, but has a defect that must be resolved
     (any `blocker` or `major` issue forces this status at minimum)
   - `ready` — scientifically sufficient and defensible as it stands

   A section with an open `blocker` or `major` issue is never `ready`.

3. `checks` are the section-specific scientific criteria. Assess each one
   honestly as `pass`, `fail`, or `unknown`. `unknown` is correct when the
   material does not let you tell — do not guess, and do not default to `pass`.
   Give a concrete `reason` referencing the material, not a restatement of the
   criterion.

4. `issues` must be specific to this research. Each needs a real scientific
   consequence in `why_it_matters` — name the conclusion that becomes unsafe.
   `recommended_action` must be something the researcher can actually do next.

5. **`evidence` must be verifiable against what you were given.** You may cite
   only:
   - research input IDs that appear in the supplied index (`#3`), and
   - item labels that appear in the supplied Research State (`H1`, `E4`, `R2`).

   You must **not** invent document structure. Do not refer to "Section 4.2",
   "Table 3", "Figure 1", page numbers, or any experiment, condition or result
   label that was not supplied to you. If the research material is an informal
   note with no sections or tables, then it has none, and citing them fabricates
   evidence.

   When the issue is an *absence*, say so directly — "no experiment in the
   supplied material varies that factor alone" — rather than attributing the
   absence to a numbered section you cannot see. Quoting the researcher's own
   wording is always safe; inventing a location for it is not.

6. Order issues by severity, most severe first. Do not manufacture issues to
   look thorough, and do not omit a blocker to be agreeable.

7. `missing_information` is what the researcher must supply to strengthen this
   section. Be exact: "per-seed accuracy for the 3 runs of E2, with variance",
   not "more experimental detail".

8. Avoid generic limitations and generic advice. If a criticism would apply
   unchanged to an arbitrary paper in this field, it does not belong here.

9. Judge the section on its own scientific purpose, but flag when it is
   inconsistent with the sections it depends on.
