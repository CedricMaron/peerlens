# REVIEW — Findings

Assess whether each finding actually follows from the results.

## Criteria to assess

1. **Traceability** — for every finding, name the specific results that support
   it. A finding with no supporting result is at least a `major` issue and often
   a `blocker` if a claim depends on it.
2. **Inferential distance** — does the finding restate what was observed, or add
   an interpretive step? Name the step explicitly. Interpretation is legitimate;
   unmarked interpretation is not.
3. **Scope match** — is the finding stated over exactly the conditions that were
   tested? A finding generalised beyond the tested datasets, scales, populations
   or settings must be narrowed or supported.
4. **Alternative explanations** — for each finding, state the most plausible
   alternative account of the same results, and whether the research rules it
   out. Consider at minimum: confounds in the experiment, selection effects,
   noise, and the possibility that a simpler component of the method explains
   the effect.
5. **Contradictions** — do any findings conflict with each other, with the
   results, or with supplied prior work? Conflicts that are simply not addressed
   are a defect.
6. **Mechanism vs. effect** — if the finding asserts *why* something happened,
   do the results discriminate that mechanism from alternatives, or do they only
   show *that* something happened?
7. **Negative results carried through** — do the findings reflect the results
   that did not work out, or only the favourable ones?

## Section-specific failure modes to look for

- Directional language ("substantially improves") applied to a difference the
  results cannot distinguish from variance.
- A finding about a mechanism drawn from an experiment that only measured an
  outcome.
- Findings that quietly widen scope: tested on one dataset, stated for the task.
- Post-hoc explanations for unexpected results, presented with the same
  confidence as pre-registered predictions.
- A negative result reinterpreted as a limitation of the evaluation rather than
  as evidence against the hypothesis.

For each finding, your check should state plainly whether the results support
it, support a weaker version of it, or do not support it.
