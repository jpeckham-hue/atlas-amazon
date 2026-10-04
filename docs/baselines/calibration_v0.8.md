# v0.8 relevance calibration (offline)

> **No live calls.** Strategies are simulated from answers recorded live in v0.7: fast-tier answers from the production recordings, strong-tier answers from the strong comparison and production escalations. A live escalation would batch different neighbours, so the strong answers are an approximation. Downstream results come from the real pipeline fed with each strategy's judgments. Costs are planner estimates (list prices), not measurements.

References: **fixture** (original); **proposed** (fixture superseded by Claude's proposed corrections in `tests/fixtures/reviews/v08_assessments.json`, *not* a human decision); **human** (fixture superseded by recorded review decisions; shown once `tests/fixtures/reviews/v08_human_decisions.json` has decisions).

## Risk signals on the v0.7 fast-tier answers

| Scenario | Keyword | Fast score | Signal (v0.8) | Strong answer | Fixture |
|---|---|---|---|---|---|
| book_cozy_mystery | cozy mystery books || mystery books cozy (equivalence) | true | `equivalence_conflict` | - | true |
| book_cozy_mystery | amateur sleuth (relevance) | 0.7 | `lexical_disagreement` | 0.6 | 0.8 |
| book_cozy_mystery | harbor town (relevance) | 0.8 | `setting_term` | 0.45 | 0.2 |
| book_cozy_mystery | mystery books (relevance) | 0.8 | `broad_category` | 0.75 | 0.6 |
| book_cozy_mystery | small town (relevance) | 0.7 | `setting_term` | 0.35 | 0.3 |
| physical_water_bottle | hydra water bottle (relevance) | 0.05 | `lexical_disagreement` | 0.15 | 0.3 |
| physical_water_bottle | stainless steel (relevance) | 0.85 | `incidental_description_support` | 0.65 | 0.55 |

## Agreement per type, per strategy and reference

| Scenario | Strategy | Reference | relevance | intent | entity | equivalence |
|---|---|---|---|---|---|---|
| book_cozy_mystery | v0.7 production (actual) | fixture | 8/11 | 3/4 | 3/3 | 1/1 |
| book_cozy_mystery | v0.7 production (actual) | proposed | 8/11 | 3/4 | 3/3 | 1/1 |
| book_cozy_mystery | A: risk escalation (v0.8 signals) | fixture | 10/11 | 3/4 | 3/3 | 1/1 |
| book_cozy_mystery | A: risk escalation (v0.8 signals) | proposed | 11/11 | 3/4 | 3/3 | 1/1 |
| book_cozy_mystery | B: strong tier for all relevance | fixture | 10/11 | 3/4 | 3/3 | 1/1 |
| book_cozy_mystery | B: strong tier for all relevance | proposed | 11/11 | 3/4 | 3/3 | 1/1 |
| physical_water_bottle | v0.7 production (actual) | fixture | 11/12 | 4/5 | 6/6 | 2/2 |
| physical_water_bottle | v0.7 production (actual) | proposed | 12/12 | 4/5 | 6/6 | 2/2 |
| physical_water_bottle | A: risk escalation (v0.8 signals) | fixture | 12/12 | 4/5 | 6/6 | 2/2 |
| physical_water_bottle | A: risk escalation (v0.8 signals) | proposed | 12/12 | 4/5 | 6/6 | 2/2 |
| physical_water_bottle | B: strong tier for all relevance | fixture | 12/12 | 4/5 | 6/6 | 2/2 |
| physical_water_bottle | B: strong tier for all relevance | proposed | 12/12 | 4/5 | 6/6 | 2/2 |

No human review decisions are recorded yet, so there is no *human* row.

## Cost and calls per strategy (keyword and equivalence stages)

Review themes (one strong call per scenario) are the same in every strategy and not included. *Planned* counts the batches plus the escalation calls the simulation needed.

| Scenario | Strategy | Calls (fast / strong) | Strong items | Expected cost | Worst case |
|---|---|---|---|---|---|
| book_cozy_mystery | v0.7 production (actual) | 4 (2 / 2) | 2 | measured, see live_v0.7.md | - |
| book_cozy_mystery | A: risk escalation (v0.8 signals) | 4 (2 / 2) | 5 | $0.0260 | $0.0706 |
| book_cozy_mystery | B: strong tier for all relevance | 4 (2 / 2) | 12 | $0.0272 | $0.0841 |
| physical_water_bottle | v0.7 production (actual) | 4 (3 / 1) | 2 | measured, see live_v0.7.md | - |
| physical_water_bottle | A: risk escalation (v0.8 signals) | 4 (3 / 1) | 2 | $0.0262 | $0.0837 |
| physical_water_bottle | B: strong tier for all relevance | 3 (2 / 1) | 16 | $0.0285 | $0.0996 |

## Downstream effects per strategy

### book_cozy_mystery

| # | v0.7 production (actual) | A: risk escalation (v0.8 signals) | B: strong tier for all relevance |
|---|---|---|---|
| 1 | cozy mystery (0.763) | cozy mystery (0.763) | cozy mystery (0.763) |
| 2 | amateur sleuth (0.731) | amateur sleuth (0.731) | amateur sleuth (0.731) |
| 3 | small town mystery books (0.699) | small town mystery books (0.699) | small town mystery books (0.707) |
| 4 | small town mystery (0.696) | small town mystery (0.696) | small town mystery (0.676) |
| 5 | small town murder mystery (0.682) | small town murder mystery (0.682) | cozy mystery books (0.671) |
| 6 | cozy mystery series (0.661) | cozy mystery series (0.661) | small town murder mystery (0.662) |
| 7 | cozy mystery books (0.651) | cozy mystery books (0.651) | cozy mystery series (0.661) |
| 8 | small town (0.643) | cozy mystery kindle unlimited (0.569) | mystery books (0.569) |
| 9 | harbor town (0.627) | mystery books (0.569) | cozy mystery kindle unlimited (0.529) |
| 10 | mystery books (0.589) | agatha christie cozy mystery (0.511) | small town (0.503) |
| 11 | cozy mystery kindle unlimited (0.569) | small town (0.503) | harbor town (0.487) |
| 12 | agatha christie cozy mystery (0.511) | harbor town (0.487) | agatha christie cozy mystery (0.471) |
| 13 | cozy mystery with cats (0.410) | cozy mystery with cats (0.410) | cozy mystery with cats (0.410) |

- v0.7 production (actual): recommendations ['cozy mystery', 'amateur sleuth', 'small town mystery books', 'small town mystery', 'small town murder mystery', 'cozy mystery series', 'cozy mystery books', 'small town', 'harbor town', 'mystery books']; backend `["('amateur sleuth small town mystery small town', 'small town murder mystery cozy mystery series', 'harbor town cozy mystery with cats')"]`
- A: risk escalation (v0.8 signals): recommendations ['cozy mystery', 'amateur sleuth', 'small town mystery books', 'small town mystery', 'small town murder mystery', 'cozy mystery series', 'cozy mystery books', 'mystery books']; backend `["('amateur sleuth small town mystery small town', 'small town murder mystery cozy mystery series', 'harbor town cozy mystery with cats')"]`
- B: strong tier for all relevance: recommendations ['cozy mystery', 'amateur sleuth', 'small town mystery books', 'small town mystery', 'cozy mystery books', 'small town murder mystery', 'cozy mystery series', 'mystery books', 'small town']; backend `["('amateur sleuth small town mystery small town', 'small town murder mystery cozy mystery series', 'harbor town cozy mystery with cats')"]`

### physical_water_bottle

| # | v0.7 production (actual) | A: risk escalation (v0.8 signals) | B: strong tier for all relevance |
|---|---|---|---|
| 1 | water bottle (0.805) | water bottle (0.805) | insulated water bottle (0.785) |
| 2 | double wall vacuum (0.785) | double wall vacuum (0.785) | insulated water bottle stainless steel (0.720) |
| 3 | insulated water bottle (0.785) | insulated water bottle (0.785) | water bottle (0.718) |
| 4 | leak proof (0.783) | leak proof (0.783) | water bottle 32 oz (0.715) |
| 5 | vacuum insulation (0.750) | vacuum insulation (0.750) | double wall vacuum (0.715) |
| 6 | insulated water bottle stainless steel (0.738) | insulated water bottle stainless steel (0.738) | leak proof (0.713) |
| 7 | water bottle 32 oz (0.733) | water bottle 32 oz (0.733) | vacuum insulation (0.680) |
| 8 | double wall (0.728) | double wall (0.728) | double wall (0.658) |
| 9 | stainless steel (0.689) | stainless steel (0.619) | stainless steel (0.619) |
| 10 | straw lid (0.554) | straw lid (0.554) | bpa free (0.531) |
| 11 | insulated water bottle with straw (0.545) | insulated water bottle with straw (0.545) | hydra water bottle (0.530) |
| 12 | hydra water bottle (0.530) | hydra water bottle (0.530) | insulated water bottle with straw (0.528) |
| 13 | water bottle with straw (0.520) | water bottle with straw (0.520) | water bottles for kids (0.489) |
| 14 | bpa free (0.514) | bpa free (0.514) | water bottle with straw (0.485) |
| 15 | water bottles for kids (0.471) | water bottles for kids (0.471) | straw lid (0.484) |
| 16 | bottle water (0.297) | bottle water (0.279) | bottle water (0.297) |

- v0.7 production (actual): recommendations ['double wall vacuum', 'insulated water bottle', 'leak proof', 'vacuum insulation', 'insulated water bottle stainless steel', 'double wall', 'straw lid']; backend `['double wall vacuum insulated insulation straw bpa free kids flask gym hiking']`
- A: risk escalation (v0.8 signals): recommendations ['double wall vacuum', 'insulated water bottle', 'leak proof', 'vacuum insulation', 'insulated water bottle stainless steel', 'double wall', 'straw lid']; backend `['double wall vacuum insulated insulation straw bpa free kids flask gym hiking']`
- B: strong tier for all relevance: recommendations ['insulated water bottle', 'insulated water bottle stainless steel', 'double wall vacuum', 'leak proof', 'vacuum insulation', 'double wall', 'bpa free']; backend `['insulated double wall vacuum insulation bpa free straw kids flask gym hiking']`

## Disagreement classification (Claude's assessment, pending human review)

| Scenario | Type | Keyword | Class | Fixture | v0.7 fast | v0.7 strong | Proposed |
|---|---|---|---|---|---|---|---|
| book_cozy_mystery | relevance | harbor town | ambiguous | 0.2 | 0.8 | 0.45 | {"score": 0.4} |
| book_cozy_mystery | relevance | small town | model_error | 0.3 | 0.7 | 0.35 | keep fixture |
| book_cozy_mystery | relevance | mystery books | model_error | 0.6 | 0.8 | 0.75 | keep fixture |
| book_cozy_mystery | relevance | amateur sleuth | ambiguous | 0.8 | 0.7 | 0.6 | keep fixture |
| book_cozy_mystery | intent | small town mystery | model_error | commercial_investigation 0.7 | transactional 0.8 | commercial_investigation 0.55 | keep fixture |
| book_cozy_mystery | intent | cozy mystery books | ambiguous | transactional 0.85 | transactional 0.8 | commercial_investigation 0.6 | keep fixture |
| physical_water_bottle | intent | bottle water | model_error | transactional 0.8 | informational 0.1 | informational 0.15 | keep fixture |
| physical_water_bottle | relevance | stainless steel | stale_reference | 0.55 | 0.85 | 0.65 | {"score": 0.65} |

Totals: {'ambiguous': 3, 'model_error': 4, 'stale_reference': 1}. Details and every rationale: [docs/reviews/judgment_review_v0.8.md](../reviews/judgment_review_v0.8.md).
