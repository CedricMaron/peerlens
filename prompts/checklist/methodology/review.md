# REVIEW — Methodology

Assess whether the methodology can actually answer the research question and
test the hypotheses, and whether its comparisons are fair.

## Criteria to assess

1. **Fitness for the question** — trace it explicitly: given this design, if the
   hypothesis is true, what is observed? If it is false, what is observed? If
   both give the same observation, the methodology cannot answer the question,
   and that is a `blocker`.
2. **Controls** — is there a condition that isolates the variable of interest?
   For each claimed mechanism, name the control that would isolate it and state
   whether it exists.
3. **Confounders** — what varies alongside the independent variable? Consider
   at minimum: capacity/parameter count, compute budget, training data, tuning
   effort, implementation quality, randomness, and evaluation conditions.
4. **Comparison fairness** — are comparators given equivalent tuning, data,
   compute and implementation care? Unequal effort is the most common source of
   inflated improvements, and is frequently invisible unless asked about
   directly.
5. **Baselines** — are the standard and the strongest available comparators
   included? A method compared only against weak or dated baselines cannot
   support a state-of-the-art claim.
6. **Reproducibility** — could a competent independent researcher rerun this?
   Check: data provenance and splits, preprocessing, hyperparameters, seeds and
   number of runs, software/hardware, and availability of code or data.
7. **Statistical treatment** — is variability accounted for? Are runs repeated?
   Is the intended analysis stated before the results, or chosen afterwards?
8. **Completeness** — is any step described so vaguely that a reader could not
   tell what was done?

## Section-specific failure modes to look for

- Method tuned on the test set, or model selection using the evaluation data.
- Baselines taken from other papers' reported numbers under different conditions
  and compared directly.
- The proposed method benefits from an extra component that the baselines lack,
  with the gain attributed to the conceptual contribution.
- Evaluation metric that does not measure the property the hypothesis is about.
- Single run, no variance, with small reported differences.
- Design able to establish correlation but used to answer a causal question.

For each `fail` or `unknown` on controls, confounders or comparison fairness,
raise a corresponding issue and name the specific missing condition.
