# REVIEW — Research Gap

Assess whether the gap genuinely follows from the literature and is
scientifically meaningful.

This section is where unjustified novelty claims originate, so review it
strictly.

## Criteria to assess

1. **Follows from the literature** — does the supplied prior work actually
   establish this gap, or is the gap asserted independently of it? Trace the
   inference explicitly.
2. **Closest work does not already address it** — take the nearest prior work
   and ask directly: does it already do this, or something scientifically
   equivalent? If the material does not contain enough detail about the closest
   work to answer, that is `unknown`, and it is `missing_information`.
3. **Scientific meaningfulness of the difference** — if the gap is "prior work
   did X, we do X′", is the difference scientifically consequential, or is it a
   parameter change, a different dataset, a different implementation, or a
   scale increase? Engineering differences are legitimate work but are not
   scientific gaps, and must not be presented as such.
4. **Not overstated** — is the gap's breadth supported? "No method handles
   heterogeneous clients" is almost never true and almost never needed.
5. **Specificity** — is the gap narrow enough that a study could close it?
6. **Consistency with the problem** — does closing this gap actually address the
   stated problem?

## Section-specific failure modes to look for

- **Novelty from absence of search.** The gap rests on not having found prior
  work. Flag this explicitly and at `major` severity or above: an unsuccessful
  literature search is not evidence of a gap. The required action is a targeted
  search of named venues/terms, not more argument.
- The gap is a restatement of the method ("existing work does not use our
  architecture").
- The gap is real but trivial: closing it changes no scientific conclusion.
- The gap is stated at a scale far larger than the study will close, guaranteeing
  overgeneralisation in the contribution section.
- The gap silently assumes prior work's limitations rather than demonstrating them.

If the gap rests on absence of evidence, say so in `evidence` in those terms,
and require the researcher to either supply the search or narrow the claim.
