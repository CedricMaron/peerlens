# REVIEW — Claims & Contribution

Assess whether every important claim is supported by the evidence actually
produced, and whether the contribution is real relative to the supplied prior
work.

This section is where research most often fails peer review. Be rigorous.

## Criteria to assess

1. **Evidence for every important claim** — take each claim in turn and trace it
   back: claim → findings → results → experiments. State where the chain breaks.
   A claim whose chain does not reach a result is unsupported, and that is at
   least `major`, `blocker` if it is a headline claim.
2. **Scope of claims** — compare the claim's stated scope against the conditions
   actually tested. Name every dimension where the claim exceeds the evidence:
   datasets, scales, domains, populations, hyperparameter regimes, baselines.
3. **Overgeneralisation** — is a universal claim resting on a narrow evidence
   base? A single dataset, a single architecture, or a single scale cannot
   support an unconditional claim. This is one of the most common serious
   defects; when you see it, state the exact conditional form the evidence would
   support instead.
4. **Claim strength vs. evidence strength** — does the modality match? Results
   that are directionally favourable but noisy support a hedged claim, not a
   definite one.
5. **Mechanism claims** — if the contribution asserts *why* the method works, is
   there an experiment that isolates that mechanism? Attributing an effect to a
   mechanism that was never isolated is a specific, high-severity defect.
6. **Scientific significance** — if every claim is granted, what does the field
   now know that it did not before? If the honest answer is "this particular
   system performs well on this particular setup", the contribution is narrower
   than presented.
7. **Relation to prior work** — for each contribution, check it against the
   supplied prior work. Does the closest prior work already establish this, or
   something scientifically equivalent? If the supplied literature is too thin
   to tell, that is `unknown` and belongs in `missing_information`.
8. **Implementation difference vs. scientific novelty** — is the contribution a
   new scientific insight, or a different implementation, configuration, dataset
   or engineering pipeline presented as one? Say which, plainly.

## Section-specific failure modes to look for

- Novelty justified only by not having found prior work. Never accept this.
  The correct phrasing is that no equivalent work was identified in the current
  search, and the required action is a targeted search — not a stronger claim.
- The abstract claims more than the results section supports.
- A claim supported by a finding that is itself unsupported (a two-step chain
  where neither step is evidenced).
- Contribution stated as a list of activities ("we propose, we evaluate, we
  analyse") rather than knowledge added.
- Improvement claimed against baselines that were not tuned comparably.
- The claim survives only because a negative result was omitted.

For each important claim, your check must state: supported, supported in weaker
form (give that form), or unsupported.
