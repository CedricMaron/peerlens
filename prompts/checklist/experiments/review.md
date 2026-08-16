# REVIEW — Experiments

Assess whether the experiments can discriminate between the explanations the
research needs to distinguish.

## Criteria to assess

1. **Hypothesis coverage** — for each hypothesis, is there an experiment that
   tests it? For each experiment, is it clear which hypothesis it serves?
   Experiments with no hypothesis, and hypotheses with no experiment, are both
   defects.
2. **Discriminating power** — this is the central check. For each experiment,
   identify everything that differs between the compared conditions. If more
   than one thing differs, the experiment cannot attribute the outcome to any
   single cause. Name the confounded factors explicitly and rate at least
   `major`; rate `blocker` when a main claim depends on that attribution.
3. **Missing controls** — for each claimed mechanism, name the control condition
   that would isolate it, and state whether it is present.
4. **Missing baselines** — is any obvious, competitive, or standard comparator
   absent? Consider also the trivial baseline (no method, random, majority
   class, or the unmodified base system) — its absence is common and often
   decisive.
5. **Required ablations** — for each component the method introduces, is there
   an ablation showing that component matters? A multi-component method with no
   ablations cannot attribute its gains.
6. **Evaluation coverage** — do the experiments cover the scope the hypotheses
   and claims are stated over? Note every condition that is claimed but not
   tested.
7. **Sufficiency of repetition** — are runs repeated enough for the size of the
   differences being discussed?
8. **Matched budgets** — do compared conditions have equal parameter counts,
   compute, data and tuning? If not, is the difference accounted for?

## Section-specific failure modes to look for

- Two or more changes bundled into one condition, with the improvement
  attributed to the conceptually interesting one.
- Ablations that remove a component *and* retrain differently.
- Comparators evaluated at a different scale, budget, or configuration.
- Cherry-picked conditions: the experiment grid is sparse exactly where the
  method would be expected to struggle.
- An experiment that would produce the same outcome whether or not the
  hypothesis holds.

For every experiment, state in the corresponding check whether it isolates what
it claims to isolate. This is the section where the most damaging defects in
empirical research are found.
