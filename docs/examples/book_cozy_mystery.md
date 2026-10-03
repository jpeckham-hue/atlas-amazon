# Research report: The Quiet Harbor

- Run: `run-book-001` at 2026-10-03T09:00:00+00:00 (atlas 0.3.0)
- Recipe: `book` 0.2.0 (amazon-base > book), marketplace US
- Seeds (seed_keywords attribute): cozy mystery, small town mystery
- Providers: catalog=fixture, keywords=fixture, suggestions=fixture, reviews=fixture
- Evidence fingerprint: `377d157376f4cbd9`

## Research tasks

| Priority | Task | Status | New / reused | Note |
|---|---|---|---|---|
| comparable_titles | competitor_catalog | executed | 3 / 0 | requested 3 competitor ASINs |
| reader_review_themes | competitor_reviews | executed | 3 / 0 | reviews for 4 ASINs; stored only, theme analysis needs semantic review |
| browse_categories | - | unsupported | 0 / 0 | no offline research task implements this priority yet |
| search_term_demand | search_demand | executed | 14 / 0 | suggestions for 2 seeds; metrics requested for 12 candidates |
| series_and_format_signals | - | unsupported | 0 / 0 | no offline research task implements this priority yet |

## Evidence summary

20 records. By kind: autocomplete_suggestion 2, catalog_item 3, keyword_metric 12, review_sample 3.

- Missing, asins without reviews: B0BOOK0001, B0BOOKC002

## Current listing audit: passed

- **warning** `keyword_avoid_terms`: prohibited terms: ['book'] [kdp-keywords, verified]

## Ranked keywords

| # | Keyword | Score | Relevance* | Demand | Competition (inv.) | Intent* | Competitor coverage |
|---|---|---|---|---|---|---|---|
| 1 | cozy mystery | 0.758 | 0.400 | 0.188 | 0.020 | 0.050 | 0.100 |
| 2 | small town | 0.753 | 0.400 | 0.193 | 0.010 | 0.050 | 0.100 |
| 3 | small town mystery | 0.711 | 0.400 | 0.156 | 0.080 | 0.075 | 0.000 |
| 4 | harbor town | 0.697 | 0.400 | 0.067 | 0.180 | 0.050 | 0.000 |
| 5 | cozy mystery with cats | 0.682 | 0.267 | 0.142 | 0.140 | 0.100 | 0.033 |
| 6 | small town murder mystery | 0.667 | 0.300 | 0.137 | 0.130 | 0.100 | 0.000 |
| 7 | small town mystery books | 0.654 | 0.300 | 0.134 | 0.120 | 0.100 | 0.000 |
| 8 | cozy mystery series | 0.573 | 0.267 | 0.171 | 0.060 | 0.075 | 0.000 |
| 9 | cozy mystery kindle unlimited | 0.564 | 0.200 | 0.164 | 0.100 | 0.100 | 0.000 |
| 10 | cozy mystery books | 0.550 | 0.267 | 0.178 | 0.030 | 0.075 | 0.000 |
| 11 | mystery books | 0.454 | 0.200 | 0.200 | 0.004 | 0.050 | 0.000 |
| 12 | amateur sleuth | 0.436 | 0.000 | 0.146 | 0.140 | 0.050 | 0.100 |

Cells show weighted contributions. *Heuristic placeholder (no evidence).

## Signal breakdown

### 1. cozy mystery: 0.758

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 1.000 | 1.000 | 0.40 | 0.400 | none | heuristic: 2/2 keyword terms appear in the product title/seed keywords |
| demand | 0.941 | 0.941 | 0.20 | 0.188 | `ev_032145039c2e06a55e944a02` | log1p(60000) / log1p(120000) from ev_032145039c2e06a55e944a02 |
| competition | 0.900 | 0.100 | 0.20 | 0.020 | `ev_032145039c2e06a55e944a02` | competition 0.9 from ev_032145039c2e06a55e944a02, scored as 1 - value |
| intent (heuristic) | 0.500 | 0.500 | 0.10 | 0.050 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | 1.000 | 1.000 | 0.10 | 0.100 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 3/3 competitor listings contain the phrase |

### 2. small town: 0.753

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 1.000 | 1.000 | 0.40 | 0.400 | none | heuristic: 2/2 keyword terms appear in the product title/seed keywords |
| demand | 0.965 | 0.965 | 0.20 | 0.193 | `ev_08e7fd0a971ef89dfd019482` | log1p(80000) / log1p(120000) from ev_08e7fd0a971ef89dfd019482 |
| competition | 0.950 | 0.050 | 0.20 | 0.010 | `ev_08e7fd0a971ef89dfd019482` | competition 0.95 from ev_08e7fd0a971ef89dfd019482, scored as 1 - value |
| intent (heuristic) | 0.500 | 0.500 | 0.10 | 0.050 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | 1.000 | 1.000 | 0.10 | 0.100 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 3/3 competitor listings contain the phrase |

### 3. small town mystery: 0.711

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 1.000 | 1.000 | 0.40 | 0.400 | none | heuristic: 3/3 keyword terms appear in the product title/seed keywords |
| demand | 0.779 | 0.779 | 0.20 | 0.156 | `ev_7ca4e84cf849746a7781c6cc` | log1p(9000) / log1p(120000) from ev_7ca4e84cf849746a7781c6cc |
| competition | 0.600 | 0.400 | 0.20 | 0.080 | `ev_7ca4e84cf849746a7781c6cc` | competition 0.6 from ev_7ca4e84cf849746a7781c6cc, scored as 1 - value |
| intent (heuristic) | 0.750 | 0.750 | 0.10 | 0.075 | none | heuristic: specificity proxy min(1, 3 words / 4) |
| competitor_coverage | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 4. harbor town: 0.697

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 1.000 | 1.000 | 0.40 | 0.400 | none | heuristic: 2/2 keyword terms appear in the product title/seed keywords |
| demand | 0.336 | 0.336 | 0.20 | 0.067 | `ev_41014cb601f7405ebe1aae96` | log1p(50) / log1p(120000) from ev_41014cb601f7405ebe1aae96 |
| competition | 0.100 | 0.900 | 0.20 | 0.180 | `ev_41014cb601f7405ebe1aae96` | competition 0.1 from ev_41014cb601f7405ebe1aae96, scored as 1 - value |
| intent (heuristic) | 0.500 | 0.500 | 0.10 | 0.050 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 5. cozy mystery with cats: 0.682

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.667 | 0.667 | 0.40 | 0.267 | none | heuristic: 2/3 keyword terms appear in the product title/seed keywords |
| demand | 0.709 | 0.709 | 0.20 | 0.142 | `ev_55ffac87c8a1334c175608c8` | log1p(4000) / log1p(120000) from ev_55ffac87c8a1334c175608c8 |
| competition | 0.300 | 0.700 | 0.20 | 0.140 | `ev_55ffac87c8a1334c175608c8` | competition 0.3 from ev_55ffac87c8a1334c175608c8, scored as 1 - value |
| intent (heuristic) | 1.000 | 1.000 | 0.10 | 0.100 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | 0.333 | 0.333 | 0.10 | 0.033 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 1/3 competitor listings contain the phrase |

### 6. small town murder mystery: 0.667

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.750 | 0.750 | 0.40 | 0.300 | none | heuristic: 3/4 keyword terms appear in the product title/seed keywords |
| demand | 0.685 | 0.685 | 0.20 | 0.137 | `ev_f1ac8667c062fc9bd3c6f8da` | log1p(3000) / log1p(120000) from ev_f1ac8667c062fc9bd3c6f8da |
| competition | 0.350 | 0.650 | 0.20 | 0.130 | `ev_f1ac8667c062fc9bd3c6f8da` | competition 0.35 from ev_f1ac8667c062fc9bd3c6f8da, scored as 1 - value |
| intent (heuristic) | 1.000 | 1.000 | 0.10 | 0.100 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 7. small town mystery books: 0.654

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.750 | 0.750 | 0.40 | 0.300 | none | heuristic: 3/4 keyword terms appear in the product title/seed keywords |
| demand | 0.669 | 0.669 | 0.20 | 0.134 | `ev_f6f5d59a7552836012746768` | log1p(2500) / log1p(120000) from ev_f6f5d59a7552836012746768 |
| competition | 0.400 | 0.600 | 0.20 | 0.120 | `ev_f6f5d59a7552836012746768` | competition 0.4 from ev_f6f5d59a7552836012746768, scored as 1 - value |
| intent (heuristic) | 1.000 | 1.000 | 0.10 | 0.100 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 8. cozy mystery series: 0.573

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.667 | 0.667 | 0.40 | 0.267 | none | heuristic: 2/3 keyword terms appear in the product title/seed keywords |
| demand | 0.855 | 0.855 | 0.20 | 0.171 | `ev_4d5f1b62831d4d8a5988cfd2` | log1p(22000) / log1p(120000) from ev_4d5f1b62831d4d8a5988cfd2 |
| competition | 0.700 | 0.300 | 0.20 | 0.060 | `ev_4d5f1b62831d4d8a5988cfd2` | competition 0.7 from ev_4d5f1b62831d4d8a5988cfd2, scored as 1 - value |
| intent (heuristic) | 0.750 | 0.750 | 0.10 | 0.075 | none | heuristic: specificity proxy min(1, 3 words / 4) |
| competitor_coverage | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 9. cozy mystery kindle unlimited: 0.564

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.500 | 0.500 | 0.40 | 0.200 | none | heuristic: 2/4 keyword terms appear in the product title/seed keywords |
| demand | 0.822 | 0.822 | 0.20 | 0.164 | `ev_ad1bc7fbd35e84bc8c65c180` | log1p(15000) / log1p(120000) from ev_ad1bc7fbd35e84bc8c65c180 |
| competition | 0.500 | 0.500 | 0.20 | 0.100 | `ev_ad1bc7fbd35e84bc8c65c180` | competition 0.5 from ev_ad1bc7fbd35e84bc8c65c180, scored as 1 - value |
| intent (heuristic) | 1.000 | 1.000 | 0.10 | 0.100 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 10. cozy mystery books: 0.550

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.667 | 0.667 | 0.40 | 0.267 | none | heuristic: 2/3 keyword terms appear in the product title/seed keywords |
| demand | 0.890 | 0.890 | 0.20 | 0.178 | `ev_ab17863b10dfe2ce5937850f` | log1p(33000) / log1p(120000) from ev_ab17863b10dfe2ce5937850f |
| competition | 0.850 | 0.150 | 0.20 | 0.030 | `ev_ab17863b10dfe2ce5937850f` | competition 0.85 from ev_ab17863b10dfe2ce5937850f, scored as 1 - value |
| intent (heuristic) | 0.750 | 0.750 | 0.10 | 0.075 | none | heuristic: specificity proxy min(1, 3 words / 4) |
| competitor_coverage | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 11. mystery books: 0.454

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.500 | 0.500 | 0.40 | 0.200 | none | heuristic: 1/2 keyword terms appear in the product title/seed keywords |
| demand | 1.000 | 1.000 | 0.20 | 0.200 | `ev_a7d3a0538d12a3cf522e368e` | log1p(120000) / log1p(120000) from ev_a7d3a0538d12a3cf522e368e |
| competition | 0.980 | 0.020 | 0.20 | 0.004 | `ev_a7d3a0538d12a3cf522e368e` | competition 0.98 from ev_a7d3a0538d12a3cf522e368e, scored as 1 - value |
| intent (heuristic) | 0.500 | 0.500 | 0.10 | 0.050 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 12. amateur sleuth: 0.436

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.000 | 0.000 | 0.40 | 0.000 | none | heuristic: 0/2 keyword terms appear in the product title/seed keywords |
| demand | 0.728 | 0.728 | 0.20 | 0.146 | `ev_517ce780c6a55e5b4ae27135` | log1p(5000) / log1p(120000) from ev_517ce780c6a55e5b4ae27135 |
| competition | 0.300 | 0.700 | 0.20 | 0.140 | `ev_517ce780c6a55e5b4ae27135` | competition 0.3 from ev_517ce780c6a55e5b4ae27135, scored as 1 - value |
| intent (heuristic) | 0.500 | 0.500 | 0.10 | 0.050 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | 1.000 | 1.000 | 0.10 | 0.100 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 3/3 competitor listings contain the phrase |

## Recommendations

- **placement_upgrade** `cozy mystery`: Ranked #1 (score 0.758) but found only in subtitle (placement 0.80). Consider: title. Evidence: `ev_032145039c2e06a55e944a02`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e`, `ev_982ab2f536cff485df6b3055`
- **keyword_gap** `small town`: Ranked #2 (score 0.753) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_3f25bd8e828dba5d98aeb55a`. Evidence: `ev_08e7fd0a971ef89dfd019482`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e`, `ev_982ab2f536cff485df6b3055`
- **keyword_gap** `small town mystery`: Ranked #3 (score 0.711) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_3f25bd8e828dba5d98aeb55a`. Evidence: `ev_7ca4e84cf849746a7781c6cc`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e`, `ev_982ab2f536cff485df6b3055`
- **placement_upgrade** `harbor town`: Ranked #4 (score 0.697) but found only in keywords (placement 0.40). Consider: title, subtitle. Packed by proposal `prop_3f25bd8e828dba5d98aeb55a`. Evidence: `ev_41014cb601f7405ebe1aae96`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e`, `ev_982ab2f536cff485df6b3055`
- **keyword_gap** `cozy mystery with cats`: Ranked #5 (score 0.682) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_3f25bd8e828dba5d98aeb55a`. Evidence: `ev_55ffac87c8a1334c175608c8`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e`, `ev_982ab2f536cff485df6b3055`
- **keyword_gap** `small town murder mystery`: Ranked #6 (score 0.667) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_3f25bd8e828dba5d98aeb55a`. Evidence: `ev_f1ac8667c062fc9bd3c6f8da`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e`, `ev_982ab2f536cff485df6b3055`
- **keyword_gap** `small town mystery books`: Ranked #7 (score 0.654) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Evidence: `ev_f6f5d59a7552836012746768`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e`, `ev_982ab2f536cff485df6b3055`
- **keyword_gap** `cozy mystery series`: Ranked #8 (score 0.573) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_3f25bd8e828dba5d98aeb55a`. Evidence: `ev_4d5f1b62831d4d8a5988cfd2`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e`, `ev_982ab2f536cff485df6b3055`
- **keyword_gap** `cozy mystery kindle unlimited`: Ranked #9 (score 0.564) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Evidence: `ev_ad1bc7fbd35e84bc8c65c180`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e`, `ev_982ab2f536cff485df6b3055`
- **keyword_gap** `cozy mystery books`: Ranked #10 (score 0.550) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Evidence: `ev_ab17863b10dfe2ce5937850f`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e`, `ev_982ab2f536cff485df6b3055`

## Proposals

### `prop_3f25bd8e828dba5d98aeb55a`: keywords (evidence)

Packs 7 of 12 ranked keywords, best first, into keywords (3/7 slots). Excluded: 1 in_visible_listing, 4 prohibited_term.

Proposed value: `small town small town mystery harbor town | cozy mystery with cats small town murder mystery | cozy mystery series amateur sleuth`

Validation: **VALID**

Evidence: `ev_08e7fd0a971ef89dfd019482`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e`, `ev_982ab2f536cff485df6b3055`, `ev_7ca4e84cf849746a7781c6cc`, `ev_41014cb601f7405ebe1aae96`, `ev_55ffac87c8a1334c175608c8`, `ev_f1ac8667c062fc9bd3c6f8da` (+2 more)
