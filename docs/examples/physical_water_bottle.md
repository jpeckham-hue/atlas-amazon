# Research report: Acme Insulated Water Bottle 32 oz

- Run: `run-bottle-001` at 2026-10-03T09:30:00+00:00 (atlas 0.6.0)
- Recipe: `physical-product` 0.2.0 (amazon-base > physical-product), marketplace US
- Seeds (seed_keywords attribute): water bottle, insulated water bottle
- Providers: catalog=fixture, keywords=fixture, suggestions=fixture, reviews=fixture, review_themes=fixture, judgments=fixture, human_judgments=none
- Keyword families: on
- Evidence fingerprint: `eb61771b7d64be7b`

## Research tasks

| Priority | Task | Status | New / reused | Note |
|---|---|---|---|---|
| competitor_titles | competitor_catalog | executed | 3 / 0 | requested 3 competitor ASINs |
| competitor_bullets | competitor_catalog | already_done | 0 / 0 | satisfied by an earlier priority |
| search_term_demand | search_demand | executed | 20 / 0 | suggestions for 2 seeds; metrics requested for 21 candidates |
| review_themes | competitor_reviews | executed | 11 / 0 | reviews for 4 ASINs; 3 review themes from 8 stored reviews |
| category_attributes | competitor_catalog | already_done | 0 / 0 | satisfied by an earlier priority |
| semantic | equivalence_judgments | executed | 2 / 0 | 2 requested, 2 valid model judgments |
| semantic | keyword_judgments | executed | 23 / 0 | 51 requested, 18 valid model judgments, 5 deterministic, 6 not needed (families that cannot be ranked), 28 unanswered (fallbacks apply) |

## Evidence summary

59 records. By kind: autocomplete_suggestion 2, catalog_item 3, judgment 25, keyword_metric 18, review_sample 8, review_theme 3.

- Missing, candidates without metrics: insulated water, wall vacuum, wall vacuum insulation
- Missing, asins without reviews: B0ACME0001

## Current listing audit: passed

- **warning** `backend_repetition`: backend repeats its own words: ['flask'] [sc-search-optimization, verified]

## Keyword families

- **insulated water bottle** (`fam_51fbb80f4d18f6b5`, canonical: highest search volume among members (120000)): `insulated water bottle`, `water bottle insulated`
  - `insulated water bottle` ~ `water bottle insulated` [attribute_rotation]: 'insulated' (suffix -ed) moved around the intact core 'water bottle'
- **water bottles for kids** (`fam_89abfca3cb4acbe5`, canonical: highest search volume among members (60000)): `water bottles for kids`, `kids water bottle`
  - `water bottles for kids` ~ `kids water bottle` [judgment]: equivalence judgment (fixture-judge-1, equivalence-fixture-v1, confidence 0.9): Both mean a water bottle intended for children. Evidence: `ev_1e85d9e630eb4889481c778d`
- Kept separate by judgment `ev_623184bcc218ec32d899cc6e`: `water bottle` / `bottle water`: judged not equivalent: Bottled drinking water versus a reusable container.

## Ranked keywords

| # | Keyword (family) | Score | Relevance | Demand | Competition (inv.) | Intent | Competitor coverage |
|---|---|---|---|---|---|---|---|
| 1 | insulated water bottle (+1 variant) | 0.793 | 0.332 J | 0.228 | 0.031 | 0.135 J | 0.067 |
| 2 | water bottle | 0.745 | 0.297 J | 0.250 | 0.008 | 0.090 J | 0.100 |
| 3 | double wall vacuum | 0.733 | 0.280 J | 0.154 | 0.120 | 0.112 H | 0.067 |
| 4 | leak proof | 0.715 | 0.262 J | 0.173 | 0.105 | 0.075 J | 0.100 |
| 5 | water bottle 32 oz | 0.680 | 0.280 J | 0.198 | 0.075 | 0.128 J | 0.000 |
| 6 | insulated water bottle stainless steel | 0.630 | 0.210 H | 0.180 | 0.090 | 0.150 H | 0.000 |
| 7 | insulated water bottle with straw | 0.600 | 0.140 J | 0.194 | 0.083 | 0.150 H | 0.033 |
| 8 | stainless steel | 0.584 | 0.193 J | 0.234 | 0.015 | 0.075 H | 0.067 |
| 9 | water bottles for kids (+1 variant) | 0.581 | 0.122 J | 0.220 | 0.055 | 0.150 H | 0.033 |
| 10 | water bottle with straw | 0.552 | 0.105 J | 0.219 | 0.045 | 0.150 H | 0.033 |
| 11 | straw lid | 0.494 | 0.070 J | 0.185 | 0.098 | 0.075 H | 0.067 |
| 12 | hydra water bottle | 0.480 | 0.105 J | 0.173 | 0.090 | 0.112 H | 0.000 |
| 13 | double wall | 0.413 | 0.000 H | 0.159 | 0.112 | 0.075 H | 0.067 |
| 14 | vacuum insulation | 0.402 | 0.000 H | 0.140 | 0.120 | 0.075 H | 0.067 |
| 15 | bpa free | 0.394 | 0.000 H | 0.177 | 0.075 | 0.075 H | 0.067 |
| 16 | bottle water | 0.367 | 0.017 J | 0.214 | 0.015 | 0.120 J | 0.000 |

Cells show weighted contributions. J = model judgment; R = human reviewer judgment (overrides the model); H = heuristic placeholder (no evidence); unmarked = measured evidence.

## Signal breakdown

### 1. insulated water bottle: 0.793

Family phrases: `insulated water bottle`, `water bottle insulated`

Intent label (judgment): transactional

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.950 | 0.950 | 0.35 | 0.332 | `ev_0c2afd89b880c06a57087321` | judgment ev_0c2afd89b880c06a57087321: fixture-judge-1 / relevance-fixture-v1, confidence 0.9: Exactly the product type and its key attribute. |
| demand | evidence | 0.910 | 0.910 | 0.25 | 0.228 | `ev_15dcaed51f61e9a6b1d41b04`, `ev_55405880b83009c2c09d4cf3` | log1p(120000 + 20000 = 140000) / log1p(450000) from ['ev_15dcaed51f61e9a6b1d41b04', 'ev_55405880b83009c2c09d4cf3'] |
| competition | evidence | 0.793 | 0.207 | 0.15 | 0.031 | `ev_15dcaed51f61e9a6b1d41b04`, `ev_55405880b83009c2c09d4cf3` | volume-weighted mean 0.793 from ['ev_15dcaed51f61e9a6b1d41b04', 'ev_55405880b83009c2c09d4cf3'], scored as 1 - value |
| intent | judgment | 0.900 | 0.900 | 0.15 | 0.135 | `ev_0a2dcbfe42b0c874b031ad2f` | judgment ev_0a2dcbfe42b0c874b031ad2f: fixture-judge-1 / intent-fixture-v1, confidence 0.85: Ready-to-buy product query. |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain any of 2 member phrases |

### 2. water bottle: 0.745

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.850 | 0.850 | 0.35 | 0.297 | `ev_e77e7a04ad0f103ae7c52c29` | judgment ev_e77e7a04ad0f103ae7c52c29: fixture-judge-1 / relevance-fixture-v1, confidence 0.9: The product type, unqualified. |
| demand | evidence | 1.000 | 1.000 | 0.25 | 0.250 | `ev_99b58c87b8aa6bfb925f1ea3` | log1p(450000) / log1p(450000) from ['ev_99b58c87b8aa6bfb925f1ea3'] |
| competition | evidence | 0.950 | 0.050 | 0.15 | 0.008 | `ev_99b58c87b8aa6bfb925f1ea3` | competition 0.950 from ['ev_99b58c87b8aa6bfb925f1ea3'], scored as 1 - value |
| intent | judgment | 0.600 | 0.600 | 0.15 | 0.090 | `ev_78f884733936d9df04876941` | judgment ev_78f884733936d9df04876941: fixture-judge-1 / intent-fixture-v1, confidence 0.8: Broad browsing query. |
| competitor_coverage | evidence | 1.000 | 1.000 | 0.10 | 0.100 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 3/3 competitor listings contain the phrase |

### 3. double wall vacuum: 0.733

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.800 | 0.800 | 0.35 | 0.280 | `ev_f291231d693233da14a2ca59` | judgment ev_f291231d693233da14a2ca59: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: Describes the product's insulation. |
| demand | evidence | 0.615 | 0.615 | 0.25 | 0.154 | `ev_9d5250bbe438bc5c61e9a908` | log1p(3000) / log1p(450000) from ['ev_9d5250bbe438bc5c61e9a908'] |
| competition | evidence | 0.200 | 0.800 | 0.15 | 0.120 | `ev_9d5250bbe438bc5c61e9a908` | competition 0.200 from ['ev_9d5250bbe438bc5c61e9a908'], scored as 1 - value |
| intent | heuristic | 0.750 | 0.750 | 0.15 | 0.112 | none | heuristic: specificity proxy min(1, 3 words / 4) |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 4. leak proof: 0.715

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.750 | 0.750 | 0.35 | 0.262 | `ev_e3889e58ef4921f8da45eb75` | judgment ev_e3889e58ef4921f8da45eb75: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: The listing claims a leak proof lid. |
| demand | evidence | 0.690 | 0.690 | 0.25 | 0.173 | `ev_fad466f336253d1d8ca2237d` | log1p(8000) / log1p(450000) from ['ev_fad466f336253d1d8ca2237d'] |
| competition | evidence | 0.300 | 0.700 | 0.15 | 0.105 | `ev_fad466f336253d1d8ca2237d` | competition 0.300 from ['ev_fad466f336253d1d8ca2237d'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.15 | 0.075 | `ev_644c96a4770cf93cf7e36c9f` | judgment ev_644c96a4770cf93cf7e36c9f: fixture-judge-1 / intent-fixture-v1, confidence 0.7: Attribute research. |
| competitor_coverage | evidence | 1.000 | 1.000 | 0.10 | 0.100 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 3/3 competitor listings contain the phrase |

### 5. water bottle 32 oz: 0.680

Intent label (judgment): transactional

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.800 | 0.800 | 0.35 | 0.280 | `ev_41dcd600ab3fda70c3d67fa8` | judgment ev_41dcd600ab3fda70c3d67fa8: fixture-judge-1 / relevance-fixture-v1, confidence 0.85: Matches the product's 32 oz size. |
| demand | evidence | 0.792 | 0.792 | 0.25 | 0.198 | `ev_475b71e0132c37882527e681` | log1p(30000) / log1p(450000) from ['ev_475b71e0132c37882527e681'] |
| competition | evidence | 0.500 | 0.500 | 0.15 | 0.075 | `ev_475b71e0132c37882527e681` | competition 0.500 from ['ev_475b71e0132c37882527e681'], scored as 1 - value |
| intent | judgment | 0.850 | 0.850 | 0.15 | 0.128 | `ev_ac00aaf13124604193b43ef1` | judgment ev_ac00aaf13124604193b43ef1: fixture-judge-1 / intent-fixture-v1, confidence 0.8: Size-specific purchase query. |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 0/3 competitor listings contain the phrase |

### 6. insulated water bottle stainless steel: 0.630

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | heuristic | 0.600 | 0.600 | 0.35 | 0.210 | none | heuristic: 3/5 keyword terms appear in the product title/seed keywords |
| demand | evidence | 0.722 | 0.722 | 0.25 | 0.180 | `ev_392a3ce9a9c419a6ab594166` | log1p(12000) / log1p(450000) from ['ev_392a3ce9a9c419a6ab594166'] |
| competition | evidence | 0.400 | 0.600 | 0.15 | 0.090 | `ev_392a3ce9a9c419a6ab594166` | competition 0.400 from ['ev_392a3ce9a9c419a6ab594166'], scored as 1 - value |
| intent | heuristic | 1.000 | 1.000 | 0.15 | 0.150 | none | heuristic: specificity proxy min(1, 5 words / 4) |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 0/3 competitor listings contain the phrase |

### 7. insulated water bottle with straw: 0.600

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.400 | 0.400 | 0.35 | 0.140 | `ev_e2b063b59e8600b660448457` | judgment ev_e2b063b59e8600b660448457: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: The product has a lid, not a straw. |
| demand | evidence | 0.778 | 0.778 | 0.25 | 0.194 | `ev_8ea1aeea6e6605cb8cfd5c17` | log1p(25000) / log1p(450000) from ['ev_8ea1aeea6e6605cb8cfd5c17'] |
| competition | evidence | 0.450 | 0.550 | 0.15 | 0.083 | `ev_8ea1aeea6e6605cb8cfd5c17` | competition 0.450 from ['ev_8ea1aeea6e6605cb8cfd5c17'], scored as 1 - value |
| intent | heuristic | 1.000 | 1.000 | 0.15 | 0.150 | none | heuristic: specificity proxy min(1, 5 words / 4) |
| competitor_coverage | evidence | 0.333 | 0.333 | 0.10 | 0.033 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 1/3 competitor listings contain the phrase |

### 8. stainless steel: 0.584

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.550 | 0.550 | 0.35 | 0.193 | `ev_4310b76fb50144be57cd8d12` | judgment ev_4310b76fb50144be57cd8d12: fixture-judge-1 / relevance-fixture-v1, confidence 0.7: Material match, but very generic. |
| demand | evidence | 0.938 | 0.938 | 0.25 | 0.234 | `ev_dd4002c0e8a657153adc2858` | log1p(200000) / log1p(450000) from ['ev_dd4002c0e8a657153adc2858'] |
| competition | evidence | 0.900 | 0.100 | 0.15 | 0.015 | `ev_dd4002c0e8a657153adc2858` | competition 0.900 from ['ev_dd4002c0e8a657153adc2858'], scored as 1 - value |
| intent | heuristic | 0.500 | 0.500 | 0.15 | 0.075 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 9. water bottles for kids: 0.581

Family phrases: `water bottles for kids`, `kids water bottle`

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.350 | 0.350 | 0.35 | 0.122 | `ev_110787c13af16644c85c2966` | judgment ev_110787c13af16644c85c2966: fixture-judge-1 / relevance-fixture-v1, confidence 0.7: Not positioned as a kids' bottle. |
| demand | evidence | 0.881 | 0.881 | 0.25 | 0.220 | `ev_a46145f25f3cf0cd1befe0fb`, `ev_5cd7fadd0c663aa3e7aad93b` | log1p(60000 + 35000 = 95000) / log1p(450000) from ['ev_a46145f25f3cf0cd1befe0fb', 'ev_5cd7fadd0c663aa3e7aad93b'] |
| competition | evidence | 0.632 | 0.368 | 0.15 | 0.055 | `ev_a46145f25f3cf0cd1befe0fb`, `ev_5cd7fadd0c663aa3e7aad93b` | volume-weighted mean 0.632 from ['ev_a46145f25f3cf0cd1befe0fb', 'ev_5cd7fadd0c663aa3e7aad93b'], scored as 1 - value |
| intent | heuristic | 1.000 | 1.000 | 0.15 | 0.150 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | evidence | 0.333 | 0.333 | 0.10 | 0.033 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 1/3 competitor listings contain any of 2 member phrases |

### 10. water bottle with straw: 0.552

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.300 | 0.300 | 0.35 | 0.105 | `ev_cf77824c02141c3d40b75244` | judgment ev_cf77824c02141c3d40b75244: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: Straw bottles are a different variant. |
| demand | evidence | 0.876 | 0.876 | 0.25 | 0.219 | `ev_8cd644a1a6f2b00053780bc1` | log1p(90000) / log1p(450000) from ['ev_8cd644a1a6f2b00053780bc1'] |
| competition | evidence | 0.700 | 0.300 | 0.15 | 0.045 | `ev_8cd644a1a6f2b00053780bc1` | competition 0.700 from ['ev_8cd644a1a6f2b00053780bc1'], scored as 1 - value |
| intent | heuristic | 1.000 | 1.000 | 0.15 | 0.150 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | evidence | 0.333 | 0.333 | 0.10 | 0.033 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 1/3 competitor listings contain the phrase |

### 11. straw lid: 0.494

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.200 | 0.200 | 0.35 | 0.070 | `ev_0df963b1d3731b3fd1226745` | judgment ev_0df963b1d3731b3fd1226745: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: The product has no straw lid. |
| demand | evidence | 0.739 | 0.739 | 0.25 | 0.185 | `ev_bbc9eb0091469ac753904ecd` | log1p(15000) / log1p(450000) from ['ev_bbc9eb0091469ac753904ecd'] |
| competition | evidence | 0.350 | 0.650 | 0.15 | 0.098 | `ev_bbc9eb0091469ac753904ecd` | competition 0.350 from ['ev_bbc9eb0091469ac753904ecd'], scored as 1 - value |
| intent | heuristic | 0.500 | 0.500 | 0.15 | 0.075 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 12. hydra water bottle: 0.480

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.300 | 0.300 | 0.35 | 0.105 | `ev_0ea16d27fc304cdd54157d24` | judgment ev_0ea16d27fc304cdd54157d24: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: A competitor's brand query. |
| demand | evidence | 0.690 | 0.690 | 0.25 | 0.173 | `ev_56f3efff8b83587b4237e9d0` | log1p(8000) / log1p(450000) from ['ev_56f3efff8b83587b4237e9d0'] |
| competition | evidence | 0.400 | 0.600 | 0.15 | 0.090 | `ev_56f3efff8b83587b4237e9d0` | competition 0.400 from ['ev_56f3efff8b83587b4237e9d0'], scored as 1 - value |
| intent | heuristic | 0.750 | 0.750 | 0.15 | 0.112 | none | heuristic: specificity proxy min(1, 3 words / 4) |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 0/3 competitor listings contain the phrase |

### 13. double wall: 0.413

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | heuristic | 0.000 | 0.000 | 0.35 | 0.000 | none | heuristic: 0/2 keyword terms appear in the product title/seed keywords |
| demand | evidence | 0.637 | 0.637 | 0.25 | 0.159 | `ev_ef542322b00eac38e76bd170` | log1p(4000) / log1p(450000) from ['ev_ef542322b00eac38e76bd170'] |
| competition | evidence | 0.250 | 0.750 | 0.15 | 0.112 | `ev_ef542322b00eac38e76bd170` | competition 0.250 from ['ev_ef542322b00eac38e76bd170'], scored as 1 - value |
| intent | heuristic | 0.500 | 0.500 | 0.15 | 0.075 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 14. vacuum insulation: 0.402

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | heuristic | 0.000 | 0.000 | 0.35 | 0.000 | none | heuristic: 0/2 keyword terms appear in the product title/seed keywords |
| demand | evidence | 0.562 | 0.562 | 0.25 | 0.140 | `ev_0e00bac0c3e1419e9571ec44` | log1p(1500) / log1p(450000) from ['ev_0e00bac0c3e1419e9571ec44'] |
| competition | evidence | 0.200 | 0.800 | 0.15 | 0.120 | `ev_0e00bac0c3e1419e9571ec44` | competition 0.200 from ['ev_0e00bac0c3e1419e9571ec44'], scored as 1 - value |
| intent | heuristic | 0.500 | 0.500 | 0.15 | 0.075 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 15. bpa free: 0.394

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | heuristic | 0.000 | 0.000 | 0.35 | 0.000 | none | heuristic: 0/2 keyword terms appear in the product title/seed keywords |
| demand | evidence | 0.708 | 0.708 | 0.25 | 0.177 | `ev_b7056b1e3800ee4bf7ec6a63` | log1p(10000) / log1p(450000) from ['ev_b7056b1e3800ee4bf7ec6a63'] |
| competition | evidence | 0.500 | 0.500 | 0.15 | 0.075 | `ev_b7056b1e3800ee4bf7ec6a63` | competition 0.500 from ['ev_b7056b1e3800ee4bf7ec6a63'], scored as 1 - value |
| intent | heuristic | 0.500 | 0.500 | 0.15 | 0.075 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 16. bottle water: 0.367

Intent label (judgment): transactional

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.050 | 0.050 | 0.35 | 0.017 | `ev_52ad8f96b1e891031f1c4515` | judgment ev_52ad8f96b1e891031f1c4515: fixture-judge-1 / relevance-fixture-v1, confidence 0.95: Bottled drinking water, not a container. |
| demand | evidence | 0.857 | 0.857 | 0.25 | 0.214 | `ev_b0f86f3f003846b0a5944e1b` | log1p(70000) / log1p(450000) from ['ev_b0f86f3f003846b0a5944e1b'] |
| competition | evidence | 0.900 | 0.100 | 0.15 | 0.015 | `ev_b0f86f3f003846b0a5944e1b` | competition 0.900 from ['ev_b0f86f3f003846b0a5944e1b'], scored as 1 - value |
| intent | judgment | 0.800 | 0.800 | 0.15 | 0.120 | `ev_c2ecc1cc9f7711ce890f9fbb` | judgment ev_c2ecc1cc9f7711ce890f9fbb: fixture-judge-1 / intent-fixture-v1, confidence 0.8: Buying bottled water. |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 0/3 competitor listings contain the phrase |

## Unscored keywords (missing evidence)

- insulated water: demand: missing: no keyword_metric evidence; competition: missing: no keyword_metric evidence
- wall vacuum: demand: missing: no keyword_metric evidence; competition: missing: no keyword_metric evidence
- wall vacuum insulation: demand: missing: no keyword_metric evidence; competition: missing: no keyword_metric evidence

## Semantic judgments

25 valid judgments: entity 6, equivalence 2, intent 5, relevance 12. Models/prompts: fixture-judge-1 (entity-fixture-v1); fixture-judge-1 (equivalence-fixture-v1); fixture-judge-1 (intent-fixture-v1); fixture-judge-1 (relevance-fixture-v1); rules:own_title_words (deterministic-v1).
- Entity flag: `hydra water bottle` is a brand reference (Hydra); kept out of the backend and of listing recommendations. Judgment `ev_d0bda6f2e466ab73a4c2cb02`

## Review themes

Repeated means at least 2 supporting reviews.

### Repeated positive themes

- **keeps drinks cold all day**: 3 reviews across B0COMP0001, B0COMP0002, B0COMP0003. Evidence: `ev_bbfc787b32ea0b942e2fac61`, `ev_56e0e6b87e00d35b57833510`, `ev_0ad3e9d63792c0fe395580c3`, `ev_fea2f2c7494d2bee121484ff`

### Repeated complaints

- **lid leaks**: 3 reviews across B0COMP0001, B0COMP0002. Evidence: `ev_347cd0bd5b69f0d896cadb3e`, `ev_8b2c44d94e33b1a838d0e989`, `ev_6ab5665930a5bff6f779e795`, `ev_9ab08f55fed160042f1a57e5`

### Possible listing opportunities

- Buyers of 2 competitor product(s) repeatedly report 'lid leaks' (3 reviews). Address it in the listing only if the product genuinely avoids this problem. ProductInput lists related feature(s): Leak proof lid with carry loop. Evidence: `ev_347cd0bd5b69f0d896cadb3e`, `ev_8b2c44d94e33b1a838d0e989`, `ev_6ab5665930a5bff6f779e795`, `ev_9ab08f55fed160042f1a57e5`
- Buyers of 3 competitor product(s) repeatedly value 'keeps drinks cold all day' (3 reviews). If the product offers this, make sure the listing says so. ProductInput lists related feature(s): Double wall vacuum insulation keeps drinks cold for 24 hours. Evidence: `ev_bbfc787b32ea0b942e2fac61`, `ev_56e0e6b87e00d35b57833510`, `ev_0ad3e9d63792c0fe395580c3`, `ev_fea2f2c7494d2bee121484ff`

Other themes (not repeated, or mixed/neutral): heavy (negative, 1)

## Recommendations

- **keyword_gap** `insulated water bottle`: Ranked #1 (score 0.793) but none of its 2 family phrases appears in any weighted field. Consider: title, item_highlights, bullets, description. Family variants: water bottle insulated. Packed by proposal `prop_32a617571520a23528ff65fb`. Evidence: `ev_0c2afd89b880c06a57087321`, `ev_15dcaed51f61e9a6b1d41b04`, `ev_55405880b83009c2c09d4cf3`, `ev_0a2dcbfe42b0c874b031ad2f` (+3 more)
- **keyword_gap** `double wall vacuum`: Ranked #3 (score 0.733) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Packed by proposal `prop_32a617571520a23528ff65fb`. Evidence: `ev_f291231d693233da14a2ca59`, `ev_9d5250bbe438bc5c61e9a908`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more)
- **placement_upgrade** `leak proof`: Ranked #4 (score 0.715) but found only in bullets (placement 0.60). Consider: title, item_highlights. Evidence: `ev_e3889e58ef4921f8da45eb75`, `ev_fad466f336253d1d8ca2237d`, `ev_644c96a4770cf93cf7e36c9f`, `ev_35f6d219e7c49ae7d271b453` (+2 more)
- **keyword_gap** `insulated water bottle stainless steel`: Ranked #6 (score 0.630) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Evidence: `ev_392a3ce9a9c419a6ab594166`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5`, `ev_eb2efabff59698fdccb240fd`
- **keyword_gap** `insulated water bottle with straw`: Ranked #7 (score 0.600) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Packed by proposal `prop_32a617571520a23528ff65fb`. Evidence: `ev_e2b063b59e8600b660448457`, `ev_8ea1aeea6e6605cb8cfd5c17`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more)
- **keyword_gap** `water bottles for kids`: Ranked #9 (score 0.581) but none of its 2 family phrases appears in any weighted field. Consider: title, item_highlights, bullets, description. Family variants: kids water bottle. Packed by proposal `prop_32a617571520a23528ff65fb`. Evidence: `ev_110787c13af16644c85c2966`, `ev_a46145f25f3cf0cd1befe0fb`, `ev_5cd7fadd0c663aa3e7aad93b`, `ev_35f6d219e7c49ae7d271b453` (+2 more)
- **keyword_gap** `water bottle with straw`: Ranked #10 (score 0.552) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Evidence: `ev_cf77824c02141c3d40b75244`, `ev_8cd644a1a6f2b00053780bc1`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more)

## Proposals

### `prop_32a617571520a23528ff65fb`: search_terms (evidence)

Packs 6 of 16 ranked keywords, best first, into search_terms (76/249 bytes). Excluded: 7 duplicate, 1 entity_flag, 25 in_visible_listing, 3 stopword. Skips 2 redundant family member(s) sharing their canonical's words: water bottle insulated, kids water bottle. Retains current unscored content: flask, gym, hiking.

Proposed value: `insulated double wall vacuum straw kids insulation bpa free flask gym hiking`

Validation: **VALID**

Evidence: `ev_0c2afd89b880c06a57087321`, `ev_15dcaed51f61e9a6b1d41b04`, `ev_55405880b83009c2c09d4cf3`, `ev_0a2dcbfe42b0c874b031ad2f`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5`, `ev_eb2efabff59698fdccb240fd`, `ev_f291231d693233da14a2ca59` (+8 more)
