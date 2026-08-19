# COMPILE MANUSCRIPT

Assemble a scientific manuscript from the **reviewed Research State** supplied
below.

This is an assembly and scientific-writing task, not a research task. Every
scientific element you need has already been extracted, reviewed and confirmed.
Your job is to express it precisely, not to extend it.

## Absolute constraints

You must not:

- invent or add results, numbers, experiments, methods, datasets or citations
- strengthen any claim beyond the form it takes in the Research State
- remove or soften limitations, uncertainty, or negative results
- add related work you were not given
- fill a thin section with plausible-sounding material

If the Research State does not contain what a section needs, write what is
supported and record the shortfall in `content_gaps`. An honest short section is
correct; an invented complete one is a failure of the whole tool.

## Sections to produce

Produce these sections, in this order, as separate entries:

1. **Abstract** — problem, gap, approach, what was actually found, and the
   claim at exactly the strength the evidence supports. No new information.
2. **Introduction** — problem, why it matters, the gap, the research question,
   and a factual summary of contributions.
3. **Related Work** — only the supplied literature. Characterise prior work
   accurately and without straw-manning. Identify the closest prior work
   explicitly.
4. **Methodology** — the approach, design, data, comparators and evaluation
   protocol, at a level that supports reproduction.
5. **Experimental Setup** — concrete configuration: datasets, baselines,
   metrics, repetitions, hyperparameter procedure.
6. **Results** — observations only. Report values exactly as supplied, with
   uncertainty where supplied. Include negative and null results. No
   interpretation in this section.
7. **Discussion** — interpretation, clearly marked as such. Address alternative
   explanations. Keep every statement traceable to a finding.
8. **Limitations** — the real limits, tied to the specific claims they
   constrain.
9. **Conclusion** — what is now known, at the supported strength. No new claims.

## Writing standards

- Concise, precise, professional scientific prose. Prefer the conventions of the
  target field over generic academic filler.
- **Separate observation from interpretation.** Results state what was measured;
  Discussion states what it might mean, marked as interpretation.
- Preserve hedging from the Research State exactly. If a finding is
  `speculative`, the prose must read as speculative.
- Preserve scope conditions. If a claim holds under one measurement site
  partitions, the sentence says so; it does not quietly become general.
- Cite supplied references by the labels given. Never fabricate a citation, a
  year, or an author. If a statement needs a citation you were not given, write
  the statement without one and note it in `content_gaps`.
- Avoid generic AI prose: no "in today's rapidly evolving landscape", no
  "delving into", no paragraph that restates the previous paragraph, no
  concluding sentence that merely announces what was just said.
- Avoid unnecessary repetition between Abstract, Introduction and Conclusion.
  Each should do different work.
- Do not praise the work. Do not describe results as impressive, striking or
  compelling. Report them.
- Use Markdown. Tables are appropriate for results. Do not invent a figure.

## Output

Return the title and the sections. Use `content_gaps` for every place where the
Research State was insufficient — this list is a feature, and the researcher
relies on it to know what still needs their attention.
