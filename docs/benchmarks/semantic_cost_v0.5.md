# Semantic cost benchmark: v0.4b vs v0.5

> **Estimates from synthetic recordings.** Token counts are approximated from text size (4 chars per token) and priced at list prices (pricing as of 2026-09-25). No live model was called: nothing here is a measured cost or a statement about model quality. v0.4b expected costs exclude Opus 5.5's always-on thinking tokens, so they understate v0.4b.

Regenerate with `ATLAS_REGEN_EXAMPLES=1 pytest tests/test_benchmark.py`.

## API calls

| Scenario | v0.4b calls | v0.5 calls (recorded) | v0.5 planned / expected / worst |
|---|---|---|---|
| book_cozy_mystery | 41 | 5 | 3 / 4 / 5 |
| physical_water_bottle | 60 | 6 | 4 / 5 / 6 |

## Cost per run

| Scenario | v0.4b expected | v0.5 expected (recorded) | v0.5 expected (plan) | v0.4b worst case | v0.5 worst case (recorded) | v0.5 worst case (plan) |
|---|---|---|---|---|---|---|
| book_cozy_mystery | $0.0966 | $0.0238 | $0.0238 | $3.6663 | $0.0667 | $0.0846 |
| physical_water_bottle | $0.1395 | $0.0286 | $0.0302 | $5.2554 | $0.0814 | $0.0977 |

The plan's worst case includes the escalation reserve (strong-tier calls the policy could add up to its cap); the recorded worst case prices only the calls that were made, each at its full `max_tokens`.

## Cost per judgment

| Scenario | Judgments | v0.4b expected / judgment | v0.5 expected / judgment (plan) |
|---|---|---|---|
| book_cozy_mystery | 40 | $0.0024 | $0.0006 |
| physical_water_bottle | 59 | $0.0024 | $0.0005 |

## Semantic judgments

| Scenario | Requested (v0.4b and v0.5) | Human | Deterministic | Not needed | Model | Escalated | Downstream identical |
|---|---|---|---|---|---|---|---|
| book_cozy_mystery | 40 | 2 | 1 | 0 | 37 | 4 | yes |
| physical_water_bottle | 59 | 0 | 5 | 6 | 48 | 6 | yes |

Requested judgments are the same in both versions. v0.4b sent every one of them (plus one review-theme call) to the model, one call each. v0.5 answers human decisions and deterministic questions without a model, skips relevance and intent for families that cannot be ranked, and batches the rest. "Downstream identical" compares ranking, entity flags, proposals, recommendations and families between individual and batched execution against the same scripted answers.
