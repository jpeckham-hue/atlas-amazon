# v0.9 closing pass (offline)

> **No live calls.** The v0.9 live answers (`tests/fixtures/recordings/live/v09/`) are served to the current pipeline: deterministic rules first (including the new format-word intent rule), recorded model answers for the rest, then the new feature-support gate on recommendations and backend terms.

## Agreement with the human-reviewed reference

| Scenario | Version | relevance | intent | entity | equivalence |
|---|---|---|---|---|---|
| book_cozy_mystery | v0.9 live | 10/11 | 3/4 | 3/3 | 1/1 |
| book_cozy_mystery | v0.9 closing pass | 10/11 | 4/4 | 3/3 | 1/1 |
| physical_water_bottle | v0.9 live | 12/12 | 5/5 | 6/6 | 2/2 |
| physical_water_bottle | v0.9 closing pass | 12/12 | 5/5 | 6/6 | 2/2 |

## Target judgments

| Keyword | v0.9 live | Closing pass | Source |
|---|---|---|---|
| cozy mystery books (intent) | commercial_investigation 0.7 | transactional 0.8 | rules:format_word_shopping |
| small town mystery books (intent) | commercial_investigation 0.7 | transactional 0.8 | rules:format_word_shopping |
| small town mystery (intent) | commercial_investigation 0.7 | commercial_investigation 0.7 | anthropic/claude-haiku-4.5 |
| bottle water (intent) | transactional 0.8 | transactional 0.8 | anthropic/claude-sonnet-5.5 |

## Unsupported feature keywords

### book_cozy_mystery

| Keyword | Rank | Unsupported terms | Recommended in v0.9 live | Packed in v0.9 live |
|---|---|---|---|---|
| cozy mystery with cats | 13 | cat | no | yes |

### physical_water_bottle

| Keyword | Rank | Unsupported terms | Recommended in v0.9 live | Packed in v0.9 live |
|---|---|---|---|---|
| bpa free | 9 | bpa, free | yes | yes |
| straw lid | 12 | straw | no | yes |
| insulated water bottle with straw | 13 | straw | no | no |
| water bottle with straw | 14 | straw | no | no |
| water bottles for kids | 15 | kid | no | yes |

## Downstream: v0.9 live vs closing pass

### book_cozy_mystery

- Recommendations: v0.9 live ['cozy mystery', 'amateur sleuth', 'small town mystery books', 'small town mystery', 'cozy mystery series', 'cozy mystery books', 'small town murder mystery', 'mystery books', 'small town']; closing pass ['cozy mystery', 'amateur sleuth', 'small town mystery books', 'small town mystery', 'cozy mystery series', 'cozy mystery books', 'small town murder mystery', 'mystery books', 'small town'].
- Backend proposal: v0.9 live `["('amateur sleuth small town mystery small town', 'cozy mystery series small town murder mystery', 'harbor town cozy mystery with cats')"]`; closing pass `["('amateur sleuth small town mystery small town', 'cozy mystery series small town murder mystery', 'harbor town')"]`; passes audit: True.
- Keyword families and entity blocking: unchanged ([('agatha christie cozy mystery', 'author'), ('cozy mystery kindle unlimited', 'trademark')]).

### physical_water_bottle

- Recommendations: v0.9 live ['insulated water bottle', 'double wall vacuum', 'vacuum insulation', 'leak proof', 'insulated water bottle stainless steel', 'double wall', 'bpa free']; closing pass ['insulated water bottle', 'double wall vacuum', 'vacuum insulation', 'leak proof', 'insulated water bottle stainless steel', 'double wall'].
- Backend proposal: v0.9 live `['insulated double wall vacuum insulation bpa free straw kids flask gym hiking']`; closing pass `['insulated double wall vacuum insulation flask gym hiking']`; passes audit: True.
- Keyword families and entity blocking: unchanged ([('hydra water bottle', 'brand')]).
