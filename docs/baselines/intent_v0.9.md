# v0.9 intent calibration (offline)

> **No live calls.** Routing strategies are simulated from answers recorded live in v0.7 with prompt `judgment_batch-v2` (fast answers from production, strong answers from the strong comparison and production escalations) and fed through the real pipeline. The v0.9 prompt (`judgment_batch-v3`: intent separated from relevance, with the `bottle water` and genre examples) is **not** measured here: no answers exist for it yet. Costs are planner estimates for the current prompt.

Reference: the **human-reviewed** reference (fixture judgments superseded by the decisions in `tests/fixtures/reviews/v08_human_decisions.json`).

## Agreement with the human-reviewed reference

| Scenario | Strategy | relevance | intent | entity | equivalence |
|---|---|---|---|---|---|
| book_cozy_mystery | v0.8 routing | 11/11 | 3/4 | 3/3 | 1/1 |
| book_cozy_mystery | intent-risk escalation (v0.9) | 11/11 | 4/4 | 3/3 | 1/1 |
| book_cozy_mystery | strong tier for all intent | 11/11 | 3/4 | 3/3 | 1/1 |
| physical_water_bottle | v0.8 routing | 12/12 | 4/5 | 6/6 | 2/2 |
| physical_water_bottle | intent-risk escalation (v0.9) | 12/12 | 4/5 | 6/6 | 2/2 |
| physical_water_bottle | strong tier for all intent | 12/12 | 4/5 | 6/6 | 2/2 |

## Intent judgments that differ from the human reference

| Scenario | Keyword | Reference | Fast (v2) | Strong (v2) | Escalation signal (v0.9) |
|---|---|---|---|---|---|
| book_cozy_mystery | cozy mystery books | transactional 0.85 | transactional 0.8 | commercial_investigation 0.6 | - |
| book_cozy_mystery | small town mystery | commercial_investigation 0.7 | transactional 0.8 | commercial_investigation 0.55 | genre_browse |
| physical_water_bottle | bottle water | transactional 0.8 | informational 0.1 | informational 0.15 | reordered_product_phrase |

## Intent escalations, strong-tier items and cost (keyword and equivalence stages)

| Scenario | Strategy | Intent items escalated | Strong-tier items | Calls (fast / strong) | Expected cost | Worst case |
|---|---|---|---|---|---|---|
| book_cozy_mystery | v0.8 routing | - | 5 | 4 (2 / 2) | $0.0270 | $0.0717 |
| book_cozy_mystery | intent-risk escalation (v0.9) | small town murder mystery, small town mystery | 7 | 4 (2 / 2) | $0.0284 | $0.0717 |
| book_cozy_mystery | strong tier for all intent | - | 18 | 5 (2 / 3) | $0.0355 | $0.0879 |
| physical_water_bottle | v0.8 routing | - | 2 | 4 (3 / 1) | $0.0271 | $0.0849 |
| physical_water_bottle | intent-risk escalation (v0.9) | bottle water | 3 | 4 (3 / 1) | $0.0278 | $0.0849 |
| physical_water_bottle | strong tier for all intent | - | 18 | 4 (2 / 2) | $0.0348 | $0.1019 |

## Downstream effects vs v0.8 routing

- book_cozy_mystery, intent-risk escalation (v0.9): rank moves none; recommendations unchanged; backend unchanged.
- book_cozy_mystery, strong tier for all intent: rank moves none; recommendations unchanged; backend unchanged.
- physical_water_bottle, intent-risk escalation (v0.9): rank moves none; recommendations unchanged; backend unchanged.
- physical_water_bottle, strong tier for all intent: rank moves ['insulated water bottle 3->2', 'leak proof 4->3', 'double wall vacuum 2->4', 'insulated water bottle stainless steel 6->5', 'water bottle 32 oz 7->6', 'vacuum insulation 5->7', 'water bottle with straw 13->12', 'hydra water bottle 12->13']; recommendations ['insulated water bottle', 'leak proof', 'double wall vacuum', 'insulated water bottle stainless steel', 'vacuum insulation', 'double wall', 'straw lid']; backend ['insulated double wall vacuum insulation straw bpa free kids flask gym hiking'].
