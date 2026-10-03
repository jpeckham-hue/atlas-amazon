# Research report: Acme Insulated Water Bottle 32 oz

- Run: `run-bottle-001` at 2026-10-03T09:30:00+00:00 (atlas 0.3.0)
- Recipe: `physical-product` 0.2.0 (amazon-base > physical-product), marketplace US
- Seeds (seed_keywords attribute): water bottle, insulated water bottle
- Providers: catalog=fixture, keywords=fixture, suggestions=fixture, reviews=fixture
- Evidence fingerprint: `39541aa96d9089d8`

## Research tasks

| Priority | Task | Status | New / reused | Note |
|---|---|---|---|---|
| competitor_titles | competitor_catalog | executed | 3 / 0 | requested 3 competitor ASINs |
| competitor_bullets | competitor_catalog | already_done | 0 / 0 | satisfied by an earlier priority |
| search_term_demand | search_demand | executed | 17 / 0 | suggestions for 2 seeds; metrics requested for 18 candidates |
| review_themes | competitor_reviews | executed | 3 / 0 | reviews for 4 ASINs; stored only, theme analysis needs semantic review |
| category_attributes | competitor_catalog | already_done | 0 / 0 | satisfied by an earlier priority |

## Evidence summary

23 records. By kind: autocomplete_suggestion 2, catalog_item 3, keyword_metric 15, review_sample 3.

- Missing, candidates without metrics: insulated water, wall vacuum, wall vacuum insulation
- Missing, asins without reviews: B0ACME0001, B0COMP0003

## Current listing audit: passed

- **warning** `backend_repetition`: backend repeats its own words: ['flask'] [sc-search-optimization, verified]

## Ranked keywords

| # | Keyword | Score | Relevance* | Demand | Competition (inv.) | Intent* | Competitor coverage |
|---|---|---|---|---|---|---|---|
| 1 | insulated water bottle | 0.784 | 0.350 | 0.225 | 0.030 | 0.112 | 0.067 |
| 2 | water bottle | 0.782 | 0.350 | 0.250 | 0.008 | 0.075 | 0.100 |
| 3 | water bottle 32 oz | 0.773 | 0.350 | 0.198 | 0.075 | 0.150 | 0.000 |
| 4 | insulated water bottle with straw | 0.723 | 0.262 | 0.194 | 0.083 | 0.150 | 0.033 |
| 5 | water bottle insulated | 0.690 | 0.350 | 0.190 | 0.037 | 0.112 | 0.000 |
| 6 | water bottle with straw | 0.681 | 0.233 | 0.219 | 0.045 | 0.150 | 0.033 |
| 7 | water bottles for kids | 0.680 | 0.233 | 0.211 | 0.052 | 0.150 | 0.033 |
| 8 | insulated water bottle stainless steel | 0.630 | 0.210 | 0.180 | 0.090 | 0.150 | 0.000 |
| 9 | double wall vacuum | 0.453 | 0.000 | 0.154 | 0.120 | 0.112 | 0.067 |
| 10 | leak proof | 0.453 | 0.000 | 0.173 | 0.105 | 0.075 | 0.100 |
| 11 | straw lid | 0.424 | 0.000 | 0.185 | 0.098 | 0.075 | 0.067 |
| 12 | double wall | 0.413 | 0.000 | 0.159 | 0.112 | 0.075 | 0.067 |
| 13 | vacuum insulation | 0.402 | 0.000 | 0.140 | 0.120 | 0.075 | 0.067 |
| 14 | bpa free | 0.394 | 0.000 | 0.177 | 0.075 | 0.075 | 0.067 |
| 15 | stainless steel | 0.391 | 0.000 | 0.234 | 0.015 | 0.075 | 0.067 |

Cells show weighted contributions. *Heuristic placeholder (no evidence).

## Signal breakdown

### 1. insulated water bottle: 0.784

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 1.000 | 1.000 | 0.35 | 0.350 | none | heuristic: 3/3 keyword terms appear in the product title/seed keywords |
| demand | 0.898 | 0.898 | 0.25 | 0.225 | `ev_15dcaed51f61e9a6b1d41b04` | log1p(120000) / log1p(450000) from ev_15dcaed51f61e9a6b1d41b04 |
| competition | 0.800 | 0.200 | 0.15 | 0.030 | `ev_15dcaed51f61e9a6b1d41b04` | competition 0.8 from ev_15dcaed51f61e9a6b1d41b04, scored as 1 - value |
| intent (heuristic) | 0.750 | 0.750 | 0.15 | 0.112 | none | heuristic: specificity proxy min(1, 3 words / 4) |
| competitor_coverage | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 2. water bottle: 0.782

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 1.000 | 1.000 | 0.35 | 0.350 | none | heuristic: 2/2 keyword terms appear in the product title/seed keywords |
| demand | 1.000 | 1.000 | 0.25 | 0.250 | `ev_99b58c87b8aa6bfb925f1ea3` | log1p(450000) / log1p(450000) from ev_99b58c87b8aa6bfb925f1ea3 |
| competition | 0.950 | 0.050 | 0.15 | 0.008 | `ev_99b58c87b8aa6bfb925f1ea3` | competition 0.95 from ev_99b58c87b8aa6bfb925f1ea3, scored as 1 - value |
| intent (heuristic) | 0.500 | 0.500 | 0.15 | 0.075 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | 1.000 | 1.000 | 0.10 | 0.100 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 3/3 competitor listings contain the phrase |

### 3. water bottle 32 oz: 0.773

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 1.000 | 1.000 | 0.35 | 0.350 | none | heuristic: 4/4 keyword terms appear in the product title/seed keywords |
| demand | 0.792 | 0.792 | 0.25 | 0.198 | `ev_475b71e0132c37882527e681` | log1p(30000) / log1p(450000) from ev_475b71e0132c37882527e681 |
| competition | 0.500 | 0.500 | 0.15 | 0.075 | `ev_475b71e0132c37882527e681` | competition 0.5 from ev_475b71e0132c37882527e681, scored as 1 - value |
| intent (heuristic) | 1.000 | 1.000 | 0.15 | 0.150 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | 0.000 | 0.000 | 0.10 | 0.000 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 0/3 competitor listings contain the phrase |

### 4. insulated water bottle with straw: 0.723

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.750 | 0.750 | 0.35 | 0.262 | none | heuristic: 3/4 keyword terms appear in the product title/seed keywords |
| demand | 0.778 | 0.778 | 0.25 | 0.194 | `ev_8ea1aeea6e6605cb8cfd5c17` | log1p(25000) / log1p(450000) from ev_8ea1aeea6e6605cb8cfd5c17 |
| competition | 0.450 | 0.550 | 0.15 | 0.083 | `ev_8ea1aeea6e6605cb8cfd5c17` | competition 0.45 from ev_8ea1aeea6e6605cb8cfd5c17, scored as 1 - value |
| intent (heuristic) | 1.000 | 1.000 | 0.15 | 0.150 | none | heuristic: specificity proxy min(1, 5 words / 4) |
| competitor_coverage | 0.333 | 0.333 | 0.10 | 0.033 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 1/3 competitor listings contain the phrase |

### 5. water bottle insulated: 0.690

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 1.000 | 1.000 | 0.35 | 0.350 | none | heuristic: 3/3 keyword terms appear in the product title/seed keywords |
| demand | 0.761 | 0.761 | 0.25 | 0.190 | `ev_55405880b83009c2c09d4cf3` | log1p(20000) / log1p(450000) from ev_55405880b83009c2c09d4cf3 |
| competition | 0.750 | 0.250 | 0.15 | 0.037 | `ev_55405880b83009c2c09d4cf3` | competition 0.75 from ev_55405880b83009c2c09d4cf3, scored as 1 - value |
| intent (heuristic) | 0.750 | 0.750 | 0.15 | 0.112 | none | heuristic: specificity proxy min(1, 3 words / 4) |
| competitor_coverage | 0.000 | 0.000 | 0.10 | 0.000 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 0/3 competitor listings contain the phrase |

### 6. water bottle with straw: 0.681

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.667 | 0.667 | 0.35 | 0.233 | none | heuristic: 2/3 keyword terms appear in the product title/seed keywords |
| demand | 0.876 | 0.876 | 0.25 | 0.219 | `ev_8cd644a1a6f2b00053780bc1` | log1p(90000) / log1p(450000) from ev_8cd644a1a6f2b00053780bc1 |
| competition | 0.700 | 0.300 | 0.15 | 0.045 | `ev_8cd644a1a6f2b00053780bc1` | competition 0.7 from ev_8cd644a1a6f2b00053780bc1, scored as 1 - value |
| intent (heuristic) | 1.000 | 1.000 | 0.15 | 0.150 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | 0.333 | 0.333 | 0.10 | 0.033 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 1/3 competitor listings contain the phrase |

### 7. water bottles for kids: 0.680

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.667 | 0.667 | 0.35 | 0.233 | none | heuristic: 2/3 keyword terms appear in the product title/seed keywords |
| demand | 0.845 | 0.845 | 0.25 | 0.211 | `ev_a46145f25f3cf0cd1befe0fb` | log1p(60000) / log1p(450000) from ev_a46145f25f3cf0cd1befe0fb |
| competition | 0.650 | 0.350 | 0.15 | 0.052 | `ev_a46145f25f3cf0cd1befe0fb` | competition 0.65 from ev_a46145f25f3cf0cd1befe0fb, scored as 1 - value |
| intent (heuristic) | 1.000 | 1.000 | 0.15 | 0.150 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | 0.333 | 0.333 | 0.10 | 0.033 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 1/3 competitor listings contain the phrase |

### 8. insulated water bottle stainless steel: 0.630

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.600 | 0.600 | 0.35 | 0.210 | none | heuristic: 3/5 keyword terms appear in the product title/seed keywords |
| demand | 0.722 | 0.722 | 0.25 | 0.180 | `ev_392a3ce9a9c419a6ab594166` | log1p(12000) / log1p(450000) from ev_392a3ce9a9c419a6ab594166 |
| competition | 0.400 | 0.600 | 0.15 | 0.090 | `ev_392a3ce9a9c419a6ab594166` | competition 0.4 from ev_392a3ce9a9c419a6ab594166, scored as 1 - value |
| intent (heuristic) | 1.000 | 1.000 | 0.15 | 0.150 | none | heuristic: specificity proxy min(1, 5 words / 4) |
| competitor_coverage | 0.000 | 0.000 | 0.10 | 0.000 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 0/3 competitor listings contain the phrase |

### 9. double wall vacuum: 0.453

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.000 | 0.000 | 0.35 | 0.000 | none | heuristic: 0/3 keyword terms appear in the product title/seed keywords |
| demand | 0.615 | 0.615 | 0.25 | 0.154 | `ev_9d5250bbe438bc5c61e9a908` | log1p(3000) / log1p(450000) from ev_9d5250bbe438bc5c61e9a908 |
| competition | 0.200 | 0.800 | 0.15 | 0.120 | `ev_9d5250bbe438bc5c61e9a908` | competition 0.2 from ev_9d5250bbe438bc5c61e9a908, scored as 1 - value |
| intent (heuristic) | 0.750 | 0.750 | 0.15 | 0.112 | none | heuristic: specificity proxy min(1, 3 words / 4) |
| competitor_coverage | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 10. leak proof: 0.453

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.000 | 0.000 | 0.35 | 0.000 | none | heuristic: 0/2 keyword terms appear in the product title/seed keywords |
| demand | 0.690 | 0.690 | 0.25 | 0.173 | `ev_fad466f336253d1d8ca2237d` | log1p(8000) / log1p(450000) from ev_fad466f336253d1d8ca2237d |
| competition | 0.300 | 0.700 | 0.15 | 0.105 | `ev_fad466f336253d1d8ca2237d` | competition 0.3 from ev_fad466f336253d1d8ca2237d, scored as 1 - value |
| intent (heuristic) | 0.500 | 0.500 | 0.15 | 0.075 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | 1.000 | 1.000 | 0.10 | 0.100 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 3/3 competitor listings contain the phrase |

### 11. straw lid: 0.424

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.000 | 0.000 | 0.35 | 0.000 | none | heuristic: 0/2 keyword terms appear in the product title/seed keywords |
| demand | 0.739 | 0.739 | 0.25 | 0.185 | `ev_bbc9eb0091469ac753904ecd` | log1p(15000) / log1p(450000) from ev_bbc9eb0091469ac753904ecd |
| competition | 0.350 | 0.650 | 0.15 | 0.098 | `ev_bbc9eb0091469ac753904ecd` | competition 0.35 from ev_bbc9eb0091469ac753904ecd, scored as 1 - value |
| intent (heuristic) | 0.500 | 0.500 | 0.15 | 0.075 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 12. double wall: 0.413

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.000 | 0.000 | 0.35 | 0.000 | none | heuristic: 0/2 keyword terms appear in the product title/seed keywords |
| demand | 0.637 | 0.637 | 0.25 | 0.159 | `ev_ef542322b00eac38e76bd170` | log1p(4000) / log1p(450000) from ev_ef542322b00eac38e76bd170 |
| competition | 0.250 | 0.750 | 0.15 | 0.112 | `ev_ef542322b00eac38e76bd170` | competition 0.25 from ev_ef542322b00eac38e76bd170, scored as 1 - value |
| intent (heuristic) | 0.500 | 0.500 | 0.15 | 0.075 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 13. vacuum insulation: 0.402

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.000 | 0.000 | 0.35 | 0.000 | none | heuristic: 0/2 keyword terms appear in the product title/seed keywords |
| demand | 0.562 | 0.562 | 0.25 | 0.140 | `ev_0e00bac0c3e1419e9571ec44` | log1p(1500) / log1p(450000) from ev_0e00bac0c3e1419e9571ec44 |
| competition | 0.200 | 0.800 | 0.15 | 0.120 | `ev_0e00bac0c3e1419e9571ec44` | competition 0.2 from ev_0e00bac0c3e1419e9571ec44, scored as 1 - value |
| intent (heuristic) | 0.500 | 0.500 | 0.15 | 0.075 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 14. bpa free: 0.394

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.000 | 0.000 | 0.35 | 0.000 | none | heuristic: 0/2 keyword terms appear in the product title/seed keywords |
| demand | 0.708 | 0.708 | 0.25 | 0.177 | `ev_b7056b1e3800ee4bf7ec6a63` | log1p(10000) / log1p(450000) from ev_b7056b1e3800ee4bf7ec6a63 |
| competition | 0.500 | 0.500 | 0.15 | 0.075 | `ev_b7056b1e3800ee4bf7ec6a63` | competition 0.5 from ev_b7056b1e3800ee4bf7ec6a63, scored as 1 - value |
| intent (heuristic) | 0.500 | 0.500 | 0.15 | 0.075 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 15. stainless steel: 0.391

| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|
| relevance (heuristic) | 0.000 | 0.000 | 0.35 | 0.000 | none | heuristic: 0/2 keyword terms appear in the product title/seed keywords |
| demand | 0.938 | 0.938 | 0.25 | 0.234 | `ev_dd4002c0e8a657153adc2858` | log1p(200000) / log1p(450000) from ev_dd4002c0e8a657153adc2858 |
| competition | 0.900 | 0.100 | 0.15 | 0.015 | `ev_dd4002c0e8a657153adc2858` | competition 0.9 from ev_dd4002c0e8a657153adc2858, scored as 1 - value |
| intent (heuristic) | 0.500 | 0.500 | 0.15 | 0.075 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

## Unscored keywords (missing evidence)

- insulated water: demand: missing: no keyword_metric evidence; competition: missing: no keyword_metric evidence
- wall vacuum: demand: missing: no keyword_metric evidence; competition: missing: no keyword_metric evidence
- wall vacuum insulation: demand: missing: no keyword_metric evidence; competition: missing: no keyword_metric evidence

## Recommendations

- **keyword_gap** `insulated water bottle`: Ranked #1 (score 0.784) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Packed by proposal `prop_9960820b853626b7f2ff826d`. Evidence: `ev_15dcaed51f61e9a6b1d41b04`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5`, `ev_eb2efabff59698fdccb240fd`
- **keyword_gap** `insulated water bottle with straw`: Ranked #4 (score 0.723) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Packed by proposal `prop_9960820b853626b7f2ff826d`. Evidence: `ev_8ea1aeea6e6605cb8cfd5c17`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5`, `ev_eb2efabff59698fdccb240fd`
- **keyword_gap** `water bottle insulated`: Ranked #5 (score 0.690) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Evidence: `ev_55405880b83009c2c09d4cf3`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5`, `ev_eb2efabff59698fdccb240fd`
- **keyword_gap** `water bottle with straw`: Ranked #6 (score 0.681) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Evidence: `ev_8cd644a1a6f2b00053780bc1`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5`, `ev_eb2efabff59698fdccb240fd`
- **keyword_gap** `water bottles for kids`: Ranked #7 (score 0.680) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Packed by proposal `prop_9960820b853626b7f2ff826d`. Evidence: `ev_a46145f25f3cf0cd1befe0fb`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5`, `ev_eb2efabff59698fdccb240fd`
- **keyword_gap** `insulated water bottle stainless steel`: Ranked #8 (score 0.630) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Evidence: `ev_392a3ce9a9c419a6ab594166`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5`, `ev_eb2efabff59698fdccb240fd`
- **keyword_gap** `double wall vacuum`: Ranked #9 (score 0.453) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Packed by proposal `prop_9960820b853626b7f2ff826d`. Evidence: `ev_9d5250bbe438bc5c61e9a908`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5`, `ev_eb2efabff59698fdccb240fd`
- **placement_upgrade** `leak proof`: Ranked #10 (score 0.453) but found only in bullets (placement 0.60). Consider: title, item_highlights. Evidence: `ev_fad466f336253d1d8ca2237d`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5`, `ev_eb2efabff59698fdccb240fd`

## Proposals

### `prop_9960820b853626b7f2ff826d`: search_terms (evidence)

Packs 6 of 15 ranked keywords, best first, into search_terms (76/249 bytes). Excluded: 8 duplicate, 25 in_visible_listing, 3 stopword. Retains current unscored content: flask, gym, hiking.

Proposed value: `insulated straw kids double wall vacuum insulation bpa free flask gym hiking`

Validation: **VALID**

Evidence: `ev_15dcaed51f61e9a6b1d41b04`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5`, `ev_eb2efabff59698fdccb240fd`, `ev_8ea1aeea6e6605cb8cfd5c17`, `ev_a46145f25f3cf0cd1befe0fb`, `ev_9d5250bbe438bc5c61e9a908`, `ev_0e00bac0c3e1419e9571ec44` (+1 more)
