# v0.6 live semantic baseline

> **LIVE results.** Recorded 2026-10-04 through Vercel AI Gateway, routed to Anthropic (`providerOptions.gateway.only = ["anthropic"]`): fast tier `anthropic/claude-haiku-4.5`, strong tier `anthropic/claude-sonnet-5.5`. Costs are **measured**: API-reported tokens of each recorded exchange times list price. This report is regenerated offline from the committed recordings (`tests/test_live_baseline.py`). The v0.5 benchmark (`docs/benchmarks/semantic_cost_v0.5.md`) remains a synthetic estimate.

## Measured usage

| Scenario | API calls | Fast / strong | Escalations | Cache hits | Input tok | Output tok | Measured cost | Item failures |
|---|---|---|---|---|---|---|---|---|
| book_cozy_mystery | 3 | 2 / 1 | 0 | 0 | 6755 | 2392 | $0.0225 | none |
| physical_water_bottle | 5 | 3 / 2 | 2 | 0 | 11602 | 3049 | $0.0332 | missing 2 |
| **total** | | | | | | | **$0.0557** | |

No refusals, malformed batches, transport errors or budget halts occurred.

## book_cozy_mystery

Agreement is reported per type; there is no combined score.

| Type | Compared | Agreed | Agreement | Other metrics | Missing | Extra |
|---|---|---|---|---|---|---|
| relevance | 11 | 8 | 73% | mean_absolute_error 0.135 | 0 | 0 |
| intent | 4 | 1 | 25% | mean_absolute_error 0.183 | 0 | 9 |
| entity | 3 | 2 | 67% | blocking_agreement_rate 1.000 | 0 | 10 |
| equivalence | 1 | 1 | 100% | - | 0 | 0 |

Relevance agreement means abs(score difference) <= 0.2.

## relevance disagreements

- **agatha christie cozy mystery**: fixture `0.4` vs live model `0.7`
  - fixture: Names another author. (`ev_892ba344203c6bbeb03b7caa`)
  - live model: Matches seed 'cozy mystery' but adds author comparison; generic for this specific book. (`ev_31bbf31c4481bde250acb3b2`)
- **amateur sleuth**: fixture `0.8` vs live model `0.6`
  - fixture: The protagonist is an amateur sleuth. (`ev_bb8680325702dc327ef7604b`)
  - live model: Related to mystery genre but doesn't confirm protagonist type from product info. (`ev_d40c250818ea005eb795c679`)
- **harbor town**: fixture `0.2` vs live model `0.5`
  - fixture: Echoes the title, but readers don't search it. (`ev_55dcc5add90c9915ce03988d`)
  - live model: Title includes 'Harbor'; relevance unclear without confirming story setting. (`ev_591a0503f8585511912803e8`)

## intent disagreements

- **cozy mystery**: fixture `{'label': 'commercial_investigation', 'score': 0.7}` vs live model `{'label': 'transactional', 'score': 0.9}`
  - fixture: Genre browsing. (`ev_8b676afc6e54ac3e2de275fa`)
  - live model: Direct match to seed 'cozy mystery'; highly transactional ready-to-buy query. (`ev_f7ff6b595de6baec0fa98197`)
- **mystery books**: fixture `{'label': 'commercial_investigation', 'score': 0.5}` vs live model `{'label': 'transactional', 'score': 0.75}`
  - fixture: Broad browsing. (`ev_eac829f4784299f52a7d58f7`)
  - live model: Book genre query; shopping intent but broader than specific subgenre. (`ev_3a303604727fe929d7be8321`)
- **small town mystery**: fixture `{'label': 'commercial_investigation', 'score': 0.7}` vs live model `{'label': 'transactional', 'score': 0.95}`
  - fixture: Subgenre browsing. (`ev_869af14ffaddb642bac7273c`)
  - live model: Exact seed keyword match; maximum buying intent for this query. (`ev_47f616b8c7aecd2f1427ac87`)

## entity disagreements

- **agatha christie cozy mystery**: fixture `{'label': 'author', 'entity': 'Agatha Christie'}` vs live model `{'label': 'brand', 'entity': 'Agatha Christie'}`
  - fixture: Names an author not associated with this book. (`ev_37072f32c6b954b640bf8043`)
  - live model: Agatha Christie is a famous author brand; not from product title. (`ev_e7b6f6f1bcb7fb59d4b85985`)

### Effect of each disagreement

| Type | Keyword | Effect |
|---|---|---|
| relevance | agatha christie cozy mystery | rank 9 -> 8 |
| relevance | amateur sleuth | rank 2 -> 5 |
| relevance | harbor town | rank 13 -> 10; recommended |
| intent | cozy mystery | rank 1 -> 1 |
| intent | mystery books | rank 10 -> 9 |
| intent | small town mystery | rank 7 -> 4 |
| entity | agatha christie cozy mystery | rank 9 -> 8 |

### Downstream outputs: fixture judgments vs live

| # | Fixture ranking | Live ranking |
|---|---|---|
| 1 | cozy mystery (0.758) | cozy mystery (0.778) |
| 2 | amateur sleuth (0.756) | small town mystery books (0.718) |
| 3 | small town murder mystery (0.687) | small town murder mystery (0.717) |
| 4 | small town mystery books (0.674) | small town mystery (0.711) |
| 5 | cozy mystery series (0.666) | amateur sleuth (0.706) |
| 6 | cozy mystery books (0.656) | cozy mystery series (0.676) |
| 7 | small town mystery (0.646) | cozy mystery books (0.659) |
| 8 | cozy mystery kindle unlimited (0.604) | agatha christie cozy mystery (0.616) |
| 9 | agatha christie cozy mystery (0.511) | mystery books (0.539) |
| 10 | mystery books (0.494) | harbor town (0.487) |
| 11 | small town (0.473) | cozy mystery kindle unlimited (0.484) |
| 12 | cozy mystery with cats (0.455) | small town (0.483) |
| 13 | harbor town (0.377) | cozy mystery with cats (0.435) |

- Keyword families: unchanged.
- Entity flags: fixture [('agatha christie cozy mystery', 'author'), ('cozy mystery kindle unlimited', 'trademark')]; live [('agatha christie cozy mystery', 'brand'), ('cozy mystery kindle unlimited', 'trademark')].
- Recommendations: fixture ['cozy mystery', 'amateur sleuth', 'small town murder mystery', 'small town mystery books', 'cozy mystery series', 'cozy mystery books', 'small town mystery', 'mystery books']; live ['cozy mystery', 'small town mystery books', 'small town murder mystery', 'small town mystery', 'amateur sleuth', 'cozy mystery series', 'cozy mystery books', 'mystery books', 'harbor town'].
- Backend proposal: fixture `["('amateur sleuth small town murder mystery', 'cozy mystery series small town mystery small town', 'cozy mystery with cats harbor town')"]`; live `["('small town murder mystery small town mystery', 'amateur sleuth cozy mystery series harbor town', 'small town cozy mystery with cats')"]`.
- Repeated positive themes: fixture ['clean read (no gore or swearing)']; live ['clean, cozy content without gore or swearing'].
- Repeated complaint themes: fixture ['predictable killer']; live ['killer is predictable'].
- Opportunities (theme, has first-party support): fixture [('predictable killer', False), ('clean read (no gore or swearing)', True)]; live [('killer is predictable', False), ('clean, cozy content without gore or swearing', True)].

## physical_water_bottle

Agreement is reported per type; there is no combined score.

| Type | Compared | Agreed | Agreement | Other metrics | Missing | Extra |
|---|---|---|---|---|---|---|
| relevance | 12 | 10 | 83% | mean_absolute_error 0.122 | 0 | 4 |
| intent | 5 | 3 | 60% | mean_absolute_error 0.176 | 0 | 11 |
| entity | 6 | 6 | 100% | blocking_agreement_rate 1.000 | 0 | 13 |
| equivalence | 2 | 2 | 100% | - | 0 | 0 |

Relevance agreement means abs(score difference) <= 0.2.

## relevance disagreements

- **double wall vacuum**: fixture `0.8` vs live model `0.6`
  - fixture: Describes the product's insulation. (`ev_f291231d693233da14a2ca59`)
  - live model: 'Double wall vacuum' describes insulation technology relevant to insulated bottles but not explicitly stated. (`ev_d26a84f6acb5de2cc7f9f6de`)
- **leak proof**: fixture `0.75` vs live model `0.5`
  - fixture: The listing claims a leak proof lid. (`ev_e3889e58ef4921f8da45eb75`)
  - live model: Common water bottle feature, but not stated in product title or seeds; unknown if present. (`ev_0a9b3d95e3a638600ba448d7`)

## intent disagreements

- **leak proof**: fixture `{'label': 'commercial_investigation', 'score': 0.5}` vs live model `{'label': 'transactional', 'score': 0.75}`
  - fixture: Attribute research. (`ev_644c96a4770cf93cf7e36c9f`)
  - live model: Leak-proof is a functional feature buyers seek in water bottles; strong purchase intent. (`ev_42020de3d7505ff181f41497`)
- **water bottle**: fixture `{'label': 'commercial_investigation', 'score': 0.6}` vs live model `{'label': 'transactional', 'score': 0.95}`
  - fixture: Broad browsing query. (`ev_78f884733936d9df04876941`)
  - live model: Exact product category match; highest purchase intent for this product type. (`ev_6f05a42acccb301ba52061c0`)

### Effect of each disagreement

| Type | Keyword | Effect |
|---|---|---|
| relevance | double wall vacuum | rank 3 -> 7 |
| relevance | leak proof | rank 4 -> 5 |
| intent | leak proof | rank 4 -> 5 |
| intent | water bottle | rank 2 -> 1 |

### Downstream outputs: fixture judgments vs live

| # | Fixture ranking | Live ranking |
|---|---|---|
| 1 | insulated water bottle (0.793) | water bottle (0.833) |
| 2 | water bottle (0.745) | insulated water bottle (0.785) |
| 3 | double wall vacuum (0.733) | water bottle 32 oz (0.752) |
| 4 | leak proof (0.715) | insulated water bottle stainless steel (0.685) |
| 5 | water bottle 32 oz (0.680) | leak proof (0.665) |
| 6 | insulated water bottle stainless steel (0.630) | vacuum insulation (0.657) |
| 7 | insulated water bottle with straw (0.600) | double wall vacuum (0.640) |
| 8 | stainless steel (0.584) | double wall (0.623) |
| 9 | water bottles for kids (0.581) | insulated water bottle with straw (0.605) |
| 10 | water bottle with straw (0.552) | bpa free (0.569) |
| 11 | straw lid (0.494) | stainless steel (0.566) |
| 12 | hydra water bottle (0.480) | straw lid (0.559) |
| 13 | double wall (0.413) | water bottle with straw (0.507) |
| 14 | vacuum insulation (0.402) | water bottles for kids (0.454) |
| 15 | bpa free (0.394) | hydra water bottle (0.433) |
| 16 | bottle water (0.367) | bottle water (0.427) |

- Keyword families: unchanged.
- Entity flags: fixture [('hydra water bottle', 'brand')]; live [('hydra water bottle', 'brand')].
- Recommendations: fixture ['insulated water bottle', 'double wall vacuum', 'leak proof', 'insulated water bottle stainless steel', 'insulated water bottle with straw', 'water bottles for kids', 'water bottle with straw']; live ['insulated water bottle', 'insulated water bottle stainless steel', 'leak proof', 'vacuum insulation', 'double wall vacuum', 'double wall', 'insulated water bottle with straw', 'bpa free'].
- Backend proposal: fixture `['insulated double wall vacuum straw kids insulation bpa free flask gym hiking']`; live `['insulated vacuum insulation double wall straw bpa free kids flask gym hiking']`.
- Repeated positive themes: fixture ['keeps drinks cold all day']; live ['keeps drinks cold'].
- Repeated complaint themes: fixture ['lid leaks']; live ['lid leaks'].
- Opportunities (theme, has first-party support): fixture [('lid leaks', True), ('keeps drinks cold all day', True)]; live [('lid leaks', True), ('keeps drinks cold', False)].
