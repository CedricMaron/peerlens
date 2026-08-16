# EXTRACT — Research Question

Extract the specific question(s) this research sets out to answer.

## What to extract

One item per distinct question (`Q1`, `Q2`, ...). Most studies have one primary
question and at most two or three secondary ones. If the material implies many
more, that is worth recording in `notes`.

Useful `details` keys:

- `question_form` — `descriptive`, `comparative`, `causal`, `mechanistic`,
  `predictive`, or `design`
- `population_or_setting` — where the answer is supposed to hold
- `independent_variable` — what is varied
- `dependent_variable` — what is measured
- `conditions` — constraints under which the question is posed
- `primary` — `true` for the main question
- `addresses_gap` — which gap item (by label) it closes

## Guidance

- Phrase the question as an actual question, even if the material states it as
  an objective or aim. Mark it `inferred` when you had to convert it.
- Do not merge distinct questions into one compound question, and do not split
  one question into artificial sub-questions.
- If the material contains a stated aim ("we aim to improve X") with no
  answerable question behind it, extract that faithfully rather than
  manufacturing a well-formed question.
- Link each question to the gap it addresses via an `addresses` relation.
