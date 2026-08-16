# EXTRACT — Methodology

Extract the approach used to answer the research question.

## What to extract

One item per meaningful methodological component (`M1`, `M2`, ...): the study
design, the proposed method, the data, the evaluation protocol, the comparison
strategy, the statistical treatment.

Useful `details` keys:

- `component_type` — `study_design`, `proposed_method`, `data`, `preprocessing`,
  `evaluation_protocol`, `comparison_strategy`, `statistical_analysis`,
  `implementation`
- `description` — what is actually done
- `controls` — what is held constant
- `comparators` — what it is compared against, and how those are configured
- `metrics` — what is measured, and how
- `hyperparameter_procedure` — how settings were chosen, for the method *and*
  for the comparators
- `repetitions` — seeds/runs/folds, if stated
- `reproducibility` — code, data, versions, hardware, randomisation control
- `assumptions` — what the method assumes about the data or setting

## Guidance

- Extract the evaluation protocol with as much care as the proposed method.
  Most methodological defects live in the protocol, not the method.
- Record explicitly when tuning effort for baselines is unspecified — that
  absence is one of the most consequential omissions in empirical work.
- If the material describes the method's implementation in detail but never
  states how it will be evaluated, extract that asymmetry into `notes`.
- Do not fill in standard practice on the researcher's behalf. If the material
  does not say how data was split, the split is unspecified, not "presumably
  standard".
