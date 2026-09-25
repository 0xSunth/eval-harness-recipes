# eval-harness-recipes

A reusable evaluation harness for LLM systems, built on a structured-extraction task: read a free-text recipe, produce a structured record, and measure how well the model did it.

**The harness is the point.** Recipes are the training ground, chosen because the ground truth is free: most recipe pages embed a `schema.org/Recipe` JSON-LD block, so reference data can be collected without hand-annotating hundreds of examples.

## Why this exists

A system that "works" in a demo is worth nothing until you can say *how often it is wrong*, *on which cases*, and *what it costs*. This repository is where I built the tooling to answer that, on a task simple enough that the method stays visible.

The same harness is being reused on two follow-up projects: structured extraction from French CNIL sanction decisions, and AI Act risk qualification.

## Status

Work in progress, started September 2026.

- [x] Target schema and normalization rules (`SPEC.md`)
- [x] Frozen dev/test split (`cases/split.json`)
- [ ] Target schema in code (`task/schema.py`)
- [ ] Annotated dev case set
- [ ] Normalizer and its unit tests
- [ ] Field-level comparator (precision / recall)
- [ ] Internal-coherence verifier
- [ ] Runner, report and CI

Results are published here once measured. No numbers are reported before they are.

## Method

What makes this more than a script:

- **The spec comes first.** `SPEC.md` defines what a correct answer *is* before any code exists. Two specs applied to the same model output produce two different scores, so a score without its spec is meaningless.
- **Frozen dev/test split.** Iteration happens on the dev set only; the test set is opened once, at the end.
- **Per-field metrics, not a global score.** Missing an ingredient and getting a unit wrong are different failures with different costs, measured separately as precision and recall.
- **Normalization is an explicit decision, not an implementation detail.** `25 cl` and `250 ml` are the same value; whether `2 large eggs` and `2 eggs` are the same is a judgement call, written down in `SPEC.md` with its consequence on the metric.
- **Deterministic verifiers before LLM judges.** Cheap, reliable, and they carry most of the value.
- **Internal-coherence check.** Every ingredient used in the steps must appear in the ingredient list, and the reverse. This detects hallucination *without consulting the reference*, which means it also works in production where no reference exists.
- **Sensitivity test.** A rule is deliberately removed and the suite re-run. If the score does not move, the evaluation is not measuring what it claims to.

## Results

_Pending. This section will hold per-field precision and recall with confidence intervals, an error taxonomy, and a comparison between prompt versions._

## Layout

```
cases/      annotated cases, dev/test split
harness/    generic: runner, metrics, report — knows nothing about recipes
task/       recipe-specific: schema, normalization, extraction, verifiers
tests/      unit tests for the normalizer, metrics and verifiers
SPEC.md     target schema, normalization rules, edge cases
```

The boundary is enforced, not just intended: `grep -ri "ingredient\|recipe" harness/` returns nothing. That is what makes the harness reusable on a different domain.

## Running it

```bash
uv sync
uv run pytest
uv run python -m harness.runner
```

Python 3.12, managed with `uv`.

## What this is not

Not a product. Recipe data already exists in structured form, which is precisely why it was chosen as a benchmark: free ground truth means hundreds of cases instead of twenty. The transferable asset is the harness and the method, not the extractor.

## Open questions

Decisions I could not settle alone are recorded in `OPEN-QUESTIONS.md` with their options and consequences, rather than silently resolved in code.