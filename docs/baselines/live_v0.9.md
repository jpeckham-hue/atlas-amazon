# v0.9 live confirmation

> **LIVE results**, recorded 2026-10-04 through Vercel AI Gateway (routed to Anthropic): fast tier `anthropic/claude-haiku-4.5`, strong tier `anthropic/claude-sonnet-5.5`, prompt `judgment_batch-v3`, v0.9 escalation. Production pipeline only. Costs are **measured** (API-reported tokens x list price). Regenerated offline by `tests/test_live_v09.py`. *v0.8* below is v0.8 routing simulated from the v0.7 recordings (v0.8 was never run live).

## Measured usage

| Scenario | API calls | Fast / strong | Escalations (reason) | Cache hits | Input tok | Output tok | Measured cost |
|---|---|---|---|---|---|---|---|
| book_cozy_mystery | 5 | 2 / 3 | 4 (broad_category 1, equivalence_conflict 1, lexical_disagreement 1, setting_term 1) | 0 | 13064 | 2930 | $0.0389 |
| physical_water_bottle | 5 | 3 / 2 | 3 (incidental_description_support 1, intent_structure 1, lexical_disagreement 1) | 0 | 13360 | 3284 | $0.0371 |
| **total** | | | | | | | **$0.0760** |

No item failures, refusals, transport errors or budget halts.

## Agreement with the human-reviewed reference

| Scenario | Version | relevance | intent | entity | equivalence |
|---|---|---|---|---|---|
| book_cozy_mystery | v0.8 (simulated) | 11/11 | 3/4 | 3/3 | 1/1 |
| book_cozy_mystery | v0.9 live | 10/11 | 3/4 | 3/3 | 1/1 |
| physical_water_bottle | v0.8 (simulated) | 12/12 | 4/5 | 6/6 | 2/2 |
| physical_water_bottle | v0.9 live | 12/12 | 5/5 | 6/6 | 2/2 |

## Disagreements with the reference (v0.9 live)

| Scenario | Type | Keyword | Reference | v0.9 live | Rationale |
|---|---|---|---|---|---|
| book_cozy_mystery | relevance | cozy mystery kindle unlimited | 0.6 | 0.3 | Product is cozy mystery but context doesn't state availability on Kindle Unlimited; cannot assume this feature. |
| book_cozy_mystery | intent | cozy mystery books | {'label': 'transactional', 'score': 0.85} | commercial_investigation 0.7 | Browsing cozy mystery books as a category; commercial investigation with moderate purchase intent. |

## Intent labels

| Scenario | v0.8 (simulated) | v0.9 live |
|---|---|---|
| book_cozy_mystery | commercial_investigation 7, transactional 6 | commercial_investigation 13 |
| physical_water_bottle | commercial_investigation 9, informational 1, navigational 1, transactional 5 | commercial_investigation 7, navigational 1, transactional 8 |

## Downstream outputs: v0.8 (simulated) vs v0.9 live

### book_cozy_mystery

| # | v0.8 (simulated) | v0.9 live |
|---|---|---|
| 1 | cozy mystery (0.763) | cozy mystery (0.738) |
| 2 | amateur sleuth (0.731) | amateur sleuth (0.726) |
| 3 | small town mystery books (0.699) | small town mystery books (0.684) |
| 4 | small town mystery (0.696) | small town mystery (0.666) |
| 5 | small town murder mystery (0.682) | cozy mystery series (0.656) |
| 6 | cozy mystery series (0.661) | cozy mystery books (0.641) |
| 7 | cozy mystery books (0.651) | small town murder mystery (0.637) |
| 8 | cozy mystery kindle unlimited (0.569) | mystery books (0.569) |
| 9 | mystery books (0.569) | small town (0.548) |
| 10 | agatha christie cozy mystery (0.511) | agatha christie cozy mystery (0.516) |
| 11 | small town (0.503) | harbor town (0.502) |
| 12 | harbor town (0.487) | cozy mystery kindle unlimited (0.459) |
| 13 | cozy mystery with cats (0.410) | cozy mystery with cats (0.415) |

- Keyword families: unchanged.
- Entity blocking: unchanged ([('agatha christie cozy mystery', 'author'), ('cozy mystery kindle unlimited', 'trademark')]).
- Recommendations: v0.8 ['cozy mystery', 'amateur sleuth', 'small town mystery books', 'small town mystery', 'small town murder mystery', 'cozy mystery series', 'cozy mystery books', 'mystery books']; v0.9 ['cozy mystery', 'amateur sleuth', 'small town mystery books', 'small town mystery', 'cozy mystery series', 'cozy mystery books', 'small town murder mystery', 'mystery books', 'small town'].
- Backend proposal: v0.8 `["('amateur sleuth small town mystery small town', 'small town murder mystery cozy mystery series', 'harbor town cozy mystery with cats')"]`; v0.9 `["('amateur sleuth small town mystery small town', 'cozy mystery series small town murder mystery', 'harbor town cozy mystery with cats')"]`; passes audit: True.
- Review themes: positives ['clean, cozy content without gore or swearing'], complaints ['killer is predictable']; opportunities (theme, first-party support) [('killer is predictable', False), ('clean, cozy content without gore or swearing', True)].

### physical_water_bottle

| # | v0.8 (simulated) | v0.9 live |
|---|---|---|
| 1 | water bottle (0.805) | water bottle (0.787) |
| 2 | double wall vacuum (0.785) | insulated water bottle (0.785) |
| 3 | insulated water bottle (0.785) | double wall vacuum (0.775) |
| 4 | leak proof (0.783) | vacuum insulation (0.755) |
| 5 | vacuum insulation (0.750) | leak proof (0.748) |
| 6 | insulated water bottle stainless steel (0.738) | water bottle 32 oz (0.740) |
| 7 | water bottle 32 oz (0.733) | insulated water bottle stainless steel (0.738) |
| 8 | double wall (0.728) | double wall (0.716) |
| 9 | stainless steel (0.619) | bpa free (0.581) |
| 10 | straw lid (0.554) | stainless steel (0.566) |
| 11 | insulated water bottle with straw (0.545) | hydra water bottle (0.565) |
| 12 | hydra water bottle (0.530) | straw lid (0.559) |
| 13 | water bottle with straw (0.520) | insulated water bottle with straw (0.538) |
| 14 | bpa free (0.514) | water bottle with straw (0.515) |
| 15 | water bottles for kids (0.471) | water bottles for kids (0.469) |
| 16 | bottle water (0.279) | bottle water (0.402) |

- Keyword families: unchanged.
- Entity blocking: unchanged ([('hydra water bottle', 'brand')]).
- Recommendations: v0.8 ['double wall vacuum', 'insulated water bottle', 'leak proof', 'vacuum insulation', 'insulated water bottle stainless steel', 'double wall', 'straw lid']; v0.9 ['insulated water bottle', 'double wall vacuum', 'vacuum insulation', 'leak proof', 'insulated water bottle stainless steel', 'double wall', 'bpa free'].
- Backend proposal: v0.8 `['double wall vacuum insulated insulation straw bpa free kids flask gym hiking']`; v0.9 `['insulated double wall vacuum insulation bpa free straw kids flask gym hiking']`; passes audit: True.
- Review themes: positives ['keeps drinks cold'], complaints ['lid leaks']; opportunities (theme, first-party support) [('lid leaks', True), ('keeps drinks cold', True)].
