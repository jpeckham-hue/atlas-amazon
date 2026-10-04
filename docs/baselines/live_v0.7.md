# v0.7 live semantic baseline

> **LIVE results**, recorded 2026-10-04 through Vercel AI Gateway (routed to Anthropic): fast tier `anthropic/claude-haiku-4.5`, strong tier `anthropic/claude-sonnet-5.5`. Costs are **measured** (API-reported tokens x list price). v0.6 figures are re-derived from the committed v0.6 live recordings. Regenerated offline by `tests/test_live_baseline_v07.py`.

What changed from v0.6: keyword judgments receive the seller's first-party context (features, subtitle, description, category, brand); prompt `judgment_batch-v2` treats stated context as fact and gives browse-vs-buy intent guidance; escalation uses deterministic risk signals instead of confidence.

## Measured usage

| Scenario | Production calls | Comparison calls | Fast / strong | Escalations | Input tok | Output tok | Measured cost |
|---|---|---|---|---|---|---|---|
| book_cozy_mystery | 5 | 1 | 2 / 4 | 2 | 16124 | 4599 | $0.0625 |
| physical_water_bottle | 5 | 1 | 3 / 3 | 2 | 16967 | 5706 | $0.0691 |
| **total** | | | | | | | **$0.1317** |

No item failures, refusals, transport errors, cache hits or budget halts. (A first attempt stalled at the gateway before any response and was billed nothing, as the gateway credit balance confirmed; the transport now times out after 120 s per attempt.)

## Agreement with the fixture judgments

Per type, agreed / compared. Relevance agrees when the scores differ by at most 0.2. *Strong tier* is the evaluation-only comparison on relevance and intent.

| Scenario | Type | v0.6 live | v0.7 live (production) | v0.7 strong tier |
|---|---|---|---|---|
| book_cozy_mystery | relevance | 8/11 | 8/11 | 9/11 |
| book_cozy_mystery | intent | 1/4 | 3/4 | 3/4 |
| book_cozy_mystery | entity | 2/3 | 3/3 | not run |
| book_cozy_mystery | equivalence | 1/1 | 1/1 | not run |
| physical_water_bottle | relevance | 10/12 | 11/12 | 12/12 |
| physical_water_bottle | intent | 3/5 | 4/5 | 4/5 |
| physical_water_bottle | entity | 6/6 | 6/6 | not run |
| physical_water_bottle | equivalence | 2/2 | 2/2 | not run |

## Intent labels (all live intent judgments)

| Scenario | v0.6 | v0.7 production | v0.7 strong tier |
|---|---|---|---|
| book_cozy_mystery | commercial_investigation 2, informational 1, transactional 10 | commercial_investigation 7, transactional 6 | commercial_investigation 13 |
| physical_water_bottle | commercial_investigation 4, navigational 1, transactional 11 | commercial_investigation 9, informational 1, navigational 1, transactional 5 | commercial_investigation 8, informational 1, navigational 1, transactional 6 |

## Focus keywords

| Scenario | Keyword | Type | Fixture | v0.6 | v0.7 production | v0.7 strong | v0.7 rationale |
|---|---|---|---|---|---|---|---|
| book_cozy_mystery | amateur sleuth | relevance | 0.8 | 0.6 | 0.7 | 0.6 | Bakery owner Nell Avery clearing her brother's name is an amateur sleuth premise in a cozy mystery; keyword is a subgenre term, fairly generic but fitting. |
| book_cozy_mystery | amateur sleuth | intent | - | transactional 0.8 | commercial_investigation 0.65 | commercial_investigation 0.45 | Browsing for mysteries featuring amateur detective protagonists; commercial intent to find similar books. |
| book_cozy_mystery | harbor town | relevance | 0.2 | 0.5 | 0.8 | 0.45 | Product title The Quiet Harbor and description mention ferry dock; harbor setting is core. |
| book_cozy_mystery | harbor town | intent | - | commercial_investigation 0.4 | commercial_investigation 0.6 | commercial_investigation 0.25 | Browsing mysteries set in harbor towns; modest commercial intent. |
| physical_water_bottle | double wall vacuum | relevance | 0.8 | 0.6 | 0.95 | 0.75 | Exact match to context feature: 'double wall vacuum insulation keeps drinks cold for 24 hours'. |
| physical_water_bottle | double wall vacuum | intent | - | commercial_investigation 0.6 | transactional 0.75 | commercial_investigation 0.45 | Specific search for double-wall vacuum insulation indicates ready-to-buy intent. |
| physical_water_bottle | leak proof | relevance | 0.75 | 0.5 | 0.9 | 0.7 | Leak proof lid is explicitly stated in features; directly describes a key product attribute. |
| physical_water_bottle | leak proof | intent | commercial_investigation 0.5 | transactional 0.75 | commercial_investigation 0.6 | commercial_investigation 0.4 | Leak proof is a product attribute; searching for it suggests browsing bottles with this feature rather than ready-to-buy intent. |

## Every judgment that changed from v0.6 to v0.7

Source is a heuristic attribution: *escalation* when the v0.7 answer came from the strong tier after a risk signal; *first-party context* when the keyword is stated in or better supported by the context v0.7 added, or the model's rationale cites wording that only the new context contains; otherwise the prompt change, which a single run cannot separate from run-to-run variation. *Strong agrees with fixture* shows whether the evaluation-only strong answer matches the fixture (relevance and intent only).

| Scenario | Type | Keyword | Fixture | v0.6 | v0.7 | Closer to fixture? | Source | Strong agrees with fixture |
|---|---|---|---|---|---|---|---|---|
| book_cozy_mystery | entity | agatha christie cozy mystery | author (Agatha Christie) | brand (Agatha Christie) | author (Agatha Christie) | yes | prompt/context change (not separable from run-to-run variation) | - |
| book_cozy_mystery | intent | agatha christie cozy mystery | - | transactional 0.85 | commercial_investigation 0.6 | - | prompt change (intent guidance) | - |
| book_cozy_mystery | intent | amateur sleuth | - | transactional 0.8 | commercial_investigation 0.65 | - | prompt change (intent guidance) | - |
| book_cozy_mystery | intent | cozy mystery | commercial_investigation 0.7 | transactional 0.9 | commercial_investigation 0.75 | yes | prompt change (intent guidance) | yes |
| book_cozy_mystery | intent | cozy mystery books | transactional 0.85 | transactional 0.88 | transactional 0.8 | same | prompt change (intent guidance) | no |
| book_cozy_mystery | intent | cozy mystery kindle unlimited | - | commercial_investigation 0.6 | transactional 0.65 | - | prompt change (intent guidance) | - |
| book_cozy_mystery | intent | cozy mystery series | - | transactional 0.85 | transactional 0.7 | - | prompt change (intent guidance) | - |
| book_cozy_mystery | intent | cozy mystery with cats | - | transactional 0.8 | commercial_investigation 0.55 | - | prompt change (intent guidance) | - |
| book_cozy_mystery | intent | harbor town | - | commercial_investigation 0.4 | commercial_investigation 0.6 | - | prompt change (intent guidance) | - |
| book_cozy_mystery | intent | mystery books | commercial_investigation 0.5 | transactional 0.75 | commercial_investigation 0.65 | yes | prompt change (intent guidance) | yes |
| book_cozy_mystery | intent | small town | - | informational 0.2 | commercial_investigation 0.6 | - | prompt change (intent guidance) | - |
| book_cozy_mystery | intent | small town murder mystery | - | transactional 0.9 | transactional 0.75 | - | prompt change (intent guidance) | - |
| book_cozy_mystery | intent | small town mystery | commercial_investigation 0.7 | transactional 0.95 | transactional 0.8 | same | prompt change (intent guidance) | yes |
| book_cozy_mystery | intent | small town mystery books | - | transactional 0.92 | transactional 0.85 | - | prompt change (intent guidance) | - |
| book_cozy_mystery | relevance | agatha christie cozy mystery | 0.4 | 0.7 | 0.5 | yes | prompt/context change (not separable from run-to-run variation) | yes |
| book_cozy_mystery | relevance | amateur sleuth | 0.8 | 0.6 | 0.7 | yes | escalation (strong model) + first-party context | no |
| book_cozy_mystery | relevance | cozy mystery kindle unlimited | 0.6 | 0.4 | 0.6 | same | prompt/context change (not separable from run-to-run variation) | yes |
| book_cozy_mystery | relevance | harbor town | 0.2 | 0.5 | 0.8 | same | first-party context | no |
| book_cozy_mystery | relevance | mystery books | 0.6 | 0.65 | 0.8 | no (now disagrees) | prompt/context change (not separable from run-to-run variation) | yes |
| book_cozy_mystery | relevance | small town | 0.3 | 0.4 | 0.7 | no (now disagrees) | prompt/context change (not separable from run-to-run variation) | yes |
| book_cozy_mystery | relevance | small town murder mystery | 0.8 | 0.9 | 0.85 | same | prompt/context change (not separable from run-to-run variation) | yes |
| book_cozy_mystery | relevance | small town mystery books | 0.8 | 0.93 | 0.9 | same | prompt/context change (not separable from run-to-run variation) | yes |
| physical_water_bottle | intent | bottle water | transactional 0.8 | transactional 0.85 | informational 0.1 | no (now disagrees) | prompt change (intent guidance) | no |
| physical_water_bottle | intent | bpa free | - | commercial_investigation 0.5 | commercial_investigation 0.6 | - | prompt change (intent guidance) | - |
| physical_water_bottle | intent | double wall vacuum | - | commercial_investigation 0.6 | transactional 0.75 | - | first-party context | - |
| physical_water_bottle | intent | hydra water bottle | - | navigational 0.9 | navigational 0.85 | - | prompt change (intent guidance) | - |
| physical_water_bottle | intent | insulated water bottle | transactional 0.9 | transactional 0.8 | transactional 0.85 | same | prompt change (intent guidance) | yes |
| physical_water_bottle | intent | insulated water bottle with straw | - | transactional 0.8 | transactional 0.75 | - | prompt change (intent guidance) | - |
| physical_water_bottle | intent | leak proof | commercial_investigation 0.5 | transactional 0.75 | commercial_investigation 0.6 | yes | first-party context | yes |
| physical_water_bottle | intent | straw lid | - | transactional 0.7 | commercial_investigation 0.55 | - | prompt change (intent guidance) | - |
| physical_water_bottle | intent | vacuum insulation | - | transactional 0.8 | commercial_investigation 0.6 | - | first-party context | - |
| physical_water_bottle | intent | water bottle | commercial_investigation 0.6 | transactional 0.95 | commercial_investigation 0.65 | yes | prompt change (intent guidance) | yes |
| physical_water_bottle | intent | water bottle 32 oz | transactional 0.85 | transactional 0.98 | transactional 0.85 | same | prompt change (intent guidance) | yes |
| physical_water_bottle | intent | water bottle with straw | - | transactional 0.7 | commercial_investigation 0.55 | - | prompt change (intent guidance) | - |
| physical_water_bottle | intent | water bottles for kids | - | transactional 0.5 | commercial_investigation 0.5 | - | prompt change (intent guidance) | - |
| physical_water_bottle | relevance | bottle water | 0.05 | 0.2 | 0.15 | same | escalation (strong model) + first-party context | yes |
| physical_water_bottle | relevance | bpa free | - | 0.5 | 0.3 | - | prompt/context change (not separable from run-to-run variation) | - |
| physical_water_bottle | relevance | double wall | - | 0.6 | 0.9 | - | first-party context | - |
| physical_water_bottle | relevance | double wall vacuum | 0.8 | 0.6 | 0.95 | yes | first-party context | yes |
| physical_water_bottle | relevance | hydra water bottle | 0.3 | 0.1 | 0.4 | same | escalation (strong model) | yes |
| physical_water_bottle | relevance | insulated water bottle | 0.95 | 0.97 | 0.95 | same | prompt/context change (not separable from run-to-run variation) | yes |
| physical_water_bottle | relevance | insulated water bottle stainless steel | - | 0.8 | 0.95 | - | first-party context | - |
| physical_water_bottle | relevance | insulated water bottle with straw | 0.4 | 0.5 | 0.35 | same | first-party context | yes |
| physical_water_bottle | relevance | leak proof | 0.75 | 0.5 | 0.9 | yes | first-party context | yes |
| physical_water_bottle | relevance | stainless steel | 0.55 | 0.5 | 0.85 | no (now disagrees) | first-party context | yes |
| physical_water_bottle | relevance | straw lid | 0.2 | 0.3 | 0.35 | same | first-party context | yes |
| physical_water_bottle | relevance | vacuum insulation | - | 0.6 | 0.95 | - | first-party context | - |
| physical_water_bottle | relevance | water bottle | 0.85 | 0.95 | 1 | same | prompt/context change (not separable from run-to-run variation) | yes |
| physical_water_bottle | relevance | water bottle with straw | 0.3 | 0.3 | 0.4 | same | first-party context | yes |
| physical_water_bottle | relevance | water bottles for kids | 0.35 | 0.2 | 0.25 | same | first-party context | yes |

## Downstream outputs: v0.6 live vs v0.7 live

### book_cozy_mystery

| # | Fixture ranking | v0.7 live ranking |
|---|---|---|
| 1 | cozy mystery (0.758) | cozy mystery (0.763) |
| 2 | amateur sleuth (0.756) | amateur sleuth (0.731) |
| 3 | small town murder mystery (0.687) | small town mystery books (0.699) |
| 4 | small town mystery books (0.674) | small town mystery (0.696) |
| 5 | cozy mystery series (0.666) | small town murder mystery (0.682) |
| 6 | cozy mystery books (0.656) | cozy mystery series (0.661) |
| 7 | small town mystery (0.646) | cozy mystery books (0.651) |
| 8 | cozy mystery kindle unlimited (0.604) | small town (0.643) |
| 9 | agatha christie cozy mystery (0.511) | harbor town (0.627) |
| 10 | mystery books (0.494) | mystery books (0.589) |
| 11 | small town (0.473) | cozy mystery kindle unlimited (0.569) |
| 12 | cozy mystery with cats (0.455) | agatha christie cozy mystery (0.511) |
| 13 | harbor town (0.377) | cozy mystery with cats (0.410) |

- Keyword families unchanged vs fixture: True.
- Entity flags: [('agatha christie cozy mystery', 'author'), ('cozy mystery kindle unlimited', 'trademark')] (fixture [('agatha christie cozy mystery', 'author'), ('cozy mystery kindle unlimited', 'trademark')]).
- Recommendations: ['cozy mystery', 'amateur sleuth', 'small town mystery books', 'small town mystery', 'small town murder mystery', 'cozy mystery series', 'cozy mystery books', 'small town', 'harbor town', 'mystery books'] (fixture ['cozy mystery', 'amateur sleuth', 'small town murder mystery', 'small town mystery books', 'cozy mystery series', 'cozy mystery books', 'small town mystery', 'mystery books']).
- Backend proposal: `["('amateur sleuth small town mystery small town', 'small town murder mystery cozy mystery series', 'harbor town cozy mystery with cats')"]` (fixture `["('amateur sleuth small town murder mystery', 'cozy mystery series small town mystery small town', 'cozy mystery with cats harbor town')"]`); passes audit: True.
- Review themes: positives ['clean, cozy content with no gore or swearing'], complaints ['killer is predictable']; opportunities (theme, first-party support): [('killer is predictable', False), ('clean, cozy content with no gore or swearing', True)].

### physical_water_bottle

| # | Fixture ranking | v0.7 live ranking |
|---|---|---|
| 1 | insulated water bottle (0.793) | water bottle (0.805) |
| 2 | water bottle (0.745) | double wall vacuum (0.785) |
| 3 | double wall vacuum (0.733) | insulated water bottle (0.785) |
| 4 | leak proof (0.715) | leak proof (0.783) |
| 5 | water bottle 32 oz (0.680) | vacuum insulation (0.750) |
| 6 | insulated water bottle stainless steel (0.630) | insulated water bottle stainless steel (0.738) |
| 7 | insulated water bottle with straw (0.600) | water bottle 32 oz (0.733) |
| 8 | stainless steel (0.584) | double wall (0.728) |
| 9 | water bottles for kids (0.581) | stainless steel (0.689) |
| 10 | water bottle with straw (0.552) | straw lid (0.554) |
| 11 | straw lid (0.494) | insulated water bottle with straw (0.545) |
| 12 | hydra water bottle (0.480) | hydra water bottle (0.530) |
| 13 | double wall (0.413) | water bottle with straw (0.520) |
| 14 | vacuum insulation (0.402) | bpa free (0.514) |
| 15 | bpa free (0.394) | water bottles for kids (0.471) |
| 16 | bottle water (0.367) | bottle water (0.297) |

- Keyword families unchanged vs fixture: True.
- Entity flags: [('hydra water bottle', 'brand')] (fixture [('hydra water bottle', 'brand')]).
- Recommendations: ['double wall vacuum', 'insulated water bottle', 'leak proof', 'vacuum insulation', 'insulated water bottle stainless steel', 'double wall', 'straw lid'] (fixture ['insulated water bottle', 'double wall vacuum', 'leak proof', 'insulated water bottle stainless steel', 'insulated water bottle with straw', 'water bottles for kids', 'water bottle with straw']).
- Backend proposal: `['double wall vacuum insulated insulation straw bpa free kids flask gym hiking']` (fixture `['insulated double wall vacuum straw kids insulation bpa free flask gym hiking']`); passes audit: True.
- Review themes: positives ['keeps contents cold for long periods'], complaints ['lid or straw leaks']; opportunities (theme, first-party support): [('lid or straw leaks', True), ('keeps contents cold for long periods', False)].
