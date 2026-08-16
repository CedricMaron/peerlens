# Extraction Task Rules

You are performing **EXTRACTION**, not review and not writing.

Your only question is:

> What does the available research material actually tell us about this section?

## Rules

1. Extract only what is supported by the supplied material. If the material is
   silent on this section, return `coverage: "none"`, an empty `items` list, and
   a `section_summary` that says plainly that the material does not yet address
   this section. Do not pad.

2. Every item gets a `provenance`:
   - `provided` / `extracted` — stated in the material
   - `inferred` — your reading of the material, not stated outright
   - `suggested` — your proposal; use sparingly and only when it genuinely helps

3. Every item gets `source_input_ids` pointing at the research inputs it came
   from. Inferred items may cite the inputs that motivated the inference.
   Suggested items may have no sources.

4. Labels must be short, stable and conventional for the section
   (`P1`, `L1`, `G1`, `Q1`, `H1`, `M1`, `E1`, `R1`, `F1`, `C1`, `LIM1`).
   If the researcher already uses labels (e.g. "Experiment 4", "H2"), reuse
   theirs exactly rather than renumbering.

5. Prefer several precise items over one vague blob. Prefer one honest item over
   several invented ones.

6. Use `details` for the structured fields that matter for this specific section.
   Keep keys in `snake_case`. Only include a key when the material supports it.

7. Record `relations` when the material makes a relationship explicit or clearly
   implies it — for example a hypothesis tested by an experiment, or an
   experiment producing a result. Reference other items by their label. Never
   invent a relationship to make the research look more complete than it is.

8. If the material contradicts itself, extract the contradiction into `notes`
   rather than silently choosing one version.

9. Do not correct, improve or strengthen the researcher's science during
   extraction. Represent it faithfully, including its weaknesses. Weaknesses are
   handled by the review step.

10. Preserve the researcher's own terminology and notation.
