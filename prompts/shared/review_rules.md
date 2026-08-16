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
   `evidence` must point at supplied material (by input ID or item label) or
   name the precise absence. `recommended_action` must be something the
   researcher can actually do next.

5. Order issues by severity, most severe first. Do not manufacture issues to
   look thorough, and do not omit a blocker to be agreeable.

6. `missing_information` is what the researcher must supply to strengthen this
   section. Be exact: "per-seed accuracy for the 3 runs of E2, with variance",
   not "more experimental detail".

7. Avoid generic limitations and generic advice. If a criticism would apply
   unchanged to an arbitrary paper in this field, it does not belong here.

8. Judge the section on its own scientific purpose, but flag when it is
   inconsistent with the sections it depends on.
