> **Synthetic example.** The "model" judgments here are replayed from a scripted recording (`synthetic-scripted-v1`), not from a live model. They exercise the live code path offline. Real agreement figures need a recording made with a live model.

# Research report: Acme Insulated Water Bottle 32 oz

- Run: `run-bottle-001` at 2026-10-03T09:30:00+00:00 (atlas 0.5.0)
- Recipe: `physical-product` 0.2.0 (amazon-base > physical-product), marketplace US
- Seeds (seed_keywords attribute): water bottle, insulated water bottle
- Providers: catalog=fixture, keywords=fixture, suggestions=fixture, reviews=fixture, review_themes=anthropic, judgments=anthropic, human_judgments=none
- Keyword families: on
- Evidence fingerprint: `ee4f574e992d53ff`

## Research tasks

| Priority | Task | Status | New / reused | Note |
|---|---|---|---|---|
| competitor_titles | competitor_catalog | executed | 3 / 0 | requested 3 competitor ASINs |
| competitor_bullets | competitor_catalog | already_done | 0 / 0 | satisfied by an earlier priority |
| search_term_demand | search_demand | executed | 20 / 0 | suggestions for 2 seeds; metrics requested for 21 candidates |
| review_themes | competitor_reviews | executed | 12 / 0 | reviews for 4 ASINs; 4 review themes from 8 stored reviews |
| category_attributes | competitor_catalog | already_done | 0 / 0 | satisfied by an earlier priority |
| semantic | equivalence_judgments | executed | 4 / 0 | 2 requested, 2 valid model judgments, 2 recorded LLM exchanges |
| semantic | keyword_judgments | executed | 53 / 0 | 51 requested, 46 valid model judgments, 5 deterministic, 6 not needed (families that cannot be ranked), 2 recorded LLM exchanges |

## Evidence summary

92 records. By kind: autocomplete_suggestion 2, catalog_item 3, judgment 53, keyword_metric 18, review_sample 8, review_theme 3, semantic_call 5.

- Missing, candidates without metrics: insulated water, wall vacuum, wall vacuum insulation
- Missing, asins without reviews: B0ACME0001

## Current listing audit: passed

- **warning** `backend_repetition`: backend repeats its own words: ['flask'] [sc-search-optimization, verified]

## Keyword families

- **insulated water bottle** (`fam_51fbb80f4d18f6b5`, canonical: highest search volume among members (120000)): `insulated water bottle`, `water bottle insulated`
  - `insulated water bottle` ~ `water bottle insulated` [attribute_rotation]: 'insulated' (suffix -ed) moved around the intact core 'water bottle'
- **water bottles for kids** (`fam_89abfca3cb4acbe5`, canonical: highest search volume among members (60000)): `water bottles for kids`, `kids water bottle`
  - `water bottles for kids` ~ `kids water bottle` [judgment]: equivalence judgment (synthetic-scripted-v1, judgment_batch-v1, confidence 0.9): Both mean a water bottle intended for children. Evidence: `ev_817bc6d8826bbada5b33ff07`
- Kept separate by judgment `ev_7024d195c01a2cd243dbdbcb`: `water bottle` / `bottle water`: judged not equivalent: Bottled drinking water versus a reusable container.

## Ranked keywords

| # | Keyword (family) | Score | Relevance | Demand | Competition (inv.) | Intent | Competitor coverage |
|---|---|---|---|---|---|---|---|
| 1 | insulated water bottle (+1 variant) | 0.793 | 0.332 J | 0.228 | 0.031 | 0.135 J | 0.067 |
| 2 | water bottle | 0.767 | 0.297 J | 0.250 | 0.008 | 0.112 J | 0.100 |
| 3 | leak proof | 0.715 | 0.262 J | 0.173 | 0.105 | 0.075 J | 0.100 |
| 4 | double wall vacuum | 0.695 | 0.280 J | 0.154 | 0.120 | 0.075 J | 0.067 |
| 5 | water bottle 32 oz | 0.680 | 0.280 J | 0.198 | 0.075 | 0.128 J | 0.000 |
| 6 | straw lid | 0.599 | 0.175 J | 0.185 | 0.098 | 0.075 J | 0.067 |
| 7 | double wall | 0.588 | 0.175 J | 0.159 | 0.112 | 0.075 J | 0.067 |
| 8 | stainless steel | 0.584 | 0.193 J | 0.234 | 0.015 | 0.075 J | 0.067 |
| 9 | vacuum insulation | 0.577 | 0.175 J | 0.140 | 0.120 | 0.075 J | 0.067 |
| 10 | bpa free | 0.569 | 0.175 J | 0.177 | 0.075 | 0.075 J | 0.067 |
| 11 | insulated water bottle with straw | 0.525 | 0.140 J | 0.194 | 0.083 | 0.075 J | 0.033 |
| 12 | insulated water bottle stainless steel | 0.520 | 0.175 J | 0.180 | 0.090 | 0.075 J | 0.000 |
| 13 | water bottles for kids (+1 variant) | 0.506 | 0.122 J | 0.220 | 0.055 | 0.075 J | 0.033 |
| 14 | water bottle with straw | 0.477 | 0.105 J | 0.219 | 0.045 | 0.075 J | 0.033 |
| 15 | hydra water bottle | 0.443 | 0.105 J | 0.173 | 0.090 | 0.075 J | 0.000 |
| 16 | bottle water | 0.367 | 0.017 J | 0.214 | 0.015 | 0.120 J | 0.000 |

Cells show weighted contributions. J = model judgment; R = human reviewer judgment (overrides the model); H = heuristic placeholder (no evidence); unmarked = measured evidence.

## Signal breakdown

### 1. insulated water bottle: 0.793

Family phrases: `insulated water bottle`, `water bottle insulated`

Intent label (judgment): transactional

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.950 | 0.950 | 0.35 | 0.332 | `ev_03696b6c4a2af8d1cacf3837` | judgment ev_03696b6c4a2af8d1cacf3837: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.9: Exactly the product type and its key attribute. |
| demand | evidence | 0.910 | 0.910 | 0.25 | 0.228 | `ev_15dcaed51f61e9a6b1d41b04`, `ev_55405880b83009c2c09d4cf3` | log1p(120000 + 20000 = 140000) / log1p(450000) from ['ev_15dcaed51f61e9a6b1d41b04', 'ev_55405880b83009c2c09d4cf3'] |
| competition | evidence | 0.793 | 0.207 | 0.15 | 0.031 | `ev_15dcaed51f61e9a6b1d41b04`, `ev_55405880b83009c2c09d4cf3` | volume-weighted mean 0.793 from ['ev_15dcaed51f61e9a6b1d41b04', 'ev_55405880b83009c2c09d4cf3'], scored as 1 - value |
| intent | judgment | 0.900 | 0.900 | 0.15 | 0.135 | `ev_65bd2a73cef4e176a078362d` | judgment ev_65bd2a73cef4e176a078362d: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.85: Ready-to-buy product query. |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain any of 2 member phrases |

### 2. water bottle: 0.767

Intent label (judgment): transactional

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.850 | 0.850 | 0.35 | 0.297 | `ev_7e818e9692958f63866d56c1` | judgment ev_7e818e9692958f63866d56c1: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.9: The product type, unqualified. |
| demand | evidence | 1.000 | 1.000 | 0.25 | 0.250 | `ev_99b58c87b8aa6bfb925f1ea3` | log1p(450000) / log1p(450000) from ['ev_99b58c87b8aa6bfb925f1ea3'] |
| competition | evidence | 0.950 | 0.050 | 0.15 | 0.008 | `ev_99b58c87b8aa6bfb925f1ea3` | competition 0.950 from ['ev_99b58c87b8aa6bfb925f1ea3'], scored as 1 - value |
| intent | judgment | 0.750 | 0.750 | 0.15 | 0.112 | `ev_8256f0417b139b11e93ec8ea` | judgment ev_8256f0417b139b11e93ec8ea: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Most shoppers searching this phrase buy within the session. |
| competitor_coverage | evidence | 1.000 | 1.000 | 0.10 | 0.100 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 3/3 competitor listings contain the phrase |

### 3. leak proof: 0.715

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.750 | 0.750 | 0.35 | 0.262 | `ev_cf7e3fc8b95a8a07a66eb764` | judgment ev_cf7e3fc8b95a8a07a66eb764: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.8: The listing claims a leak proof lid. |
| demand | evidence | 0.690 | 0.690 | 0.25 | 0.173 | `ev_fad466f336253d1d8ca2237d` | log1p(8000) / log1p(450000) from ['ev_fad466f336253d1d8ca2237d'] |
| competition | evidence | 0.300 | 0.700 | 0.15 | 0.105 | `ev_fad466f336253d1d8ca2237d` | competition 0.300 from ['ev_fad466f336253d1d8ca2237d'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.15 | 0.075 | `ev_7022ed0ac53723496f8dc83f` | judgment ev_7022ed0ac53723496f8dc83f: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.7: Attribute research. |
| competitor_coverage | evidence | 1.000 | 1.000 | 0.10 | 0.100 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 3/3 competitor listings contain the phrase |

### 4. double wall vacuum: 0.695

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.800 | 0.800 | 0.35 | 0.280 | `ev_24c48a691532da4532e6c514` | judgment ev_24c48a691532da4532e6c514: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.8: Describes the product's insulation. |
| demand | evidence | 0.615 | 0.615 | 0.25 | 0.154 | `ev_9d5250bbe438bc5c61e9a908` | log1p(3000) / log1p(450000) from ['ev_9d5250bbe438bc5c61e9a908'] |
| competition | evidence | 0.200 | 0.800 | 0.15 | 0.120 | `ev_9d5250bbe438bc5c61e9a908` | competition 0.200 from ['ev_9d5250bbe438bc5c61e9a908'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.15 | 0.075 | `ev_0c35a921b7b572008717b040` | judgment ev_0c35a921b7b572008717b040: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 5. water bottle 32 oz: 0.680

Intent label (judgment): transactional

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.800 | 0.800 | 0.35 | 0.280 | `ev_9ca4cbbe0a33a1a082dbf12f` | judgment ev_9ca4cbbe0a33a1a082dbf12f: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.85: Matches the product's 32 oz size. |
| demand | evidence | 0.792 | 0.792 | 0.25 | 0.198 | `ev_475b71e0132c37882527e681` | log1p(30000) / log1p(450000) from ['ev_475b71e0132c37882527e681'] |
| competition | evidence | 0.500 | 0.500 | 0.15 | 0.075 | `ev_475b71e0132c37882527e681` | competition 0.500 from ['ev_475b71e0132c37882527e681'], scored as 1 - value |
| intent | judgment | 0.850 | 0.850 | 0.15 | 0.128 | `ev_d5cd6cd16f7a05fdc09c3001` | judgment ev_d5cd6cd16f7a05fdc09c3001: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.8: Size-specific purchase query. |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 0/3 competitor listings contain the phrase |

### 6. straw lid: 0.599

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.500 | 0.500 | 0.35 | 0.175 | `ev_58b1375bc0fd4bc0c9b8e7a7` | judgment ev_58b1375bc0fd4bc0c9b8e7a7: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Straw lids are a common accessory in this category. |
| demand | evidence | 0.739 | 0.739 | 0.25 | 0.185 | `ev_bbc9eb0091469ac753904ecd` | log1p(15000) / log1p(450000) from ['ev_bbc9eb0091469ac753904ecd'] |
| competition | evidence | 0.350 | 0.650 | 0.15 | 0.098 | `ev_bbc9eb0091469ac753904ecd` | competition 0.350 from ['ev_bbc9eb0091469ac753904ecd'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.15 | 0.075 | `ev_448bd96196252660b53c4149` | judgment ev_448bd96196252660b53c4149: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 7. double wall: 0.588

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.500 | 0.500 | 0.35 | 0.175 | `ev_7b33e06554be82389269370c` | judgment ev_7b33e06554be82389269370c: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| demand | evidence | 0.637 | 0.637 | 0.25 | 0.159 | `ev_ef542322b00eac38e76bd170` | log1p(4000) / log1p(450000) from ['ev_ef542322b00eac38e76bd170'] |
| competition | evidence | 0.250 | 0.750 | 0.15 | 0.112 | `ev_ef542322b00eac38e76bd170` | competition 0.250 from ['ev_ef542322b00eac38e76bd170'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.15 | 0.075 | `ev_14cf9255cf7a65d5eccf1a84` | judgment ev_14cf9255cf7a65d5eccf1a84: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 8. stainless steel: 0.584

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.550 | 0.550 | 0.35 | 0.193 | `ev_208a081ff8bf12bbcd31796a` | judgment ev_208a081ff8bf12bbcd31796a: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.7: Material match, but very generic. |
| demand | evidence | 0.938 | 0.938 | 0.25 | 0.234 | `ev_dd4002c0e8a657153adc2858` | log1p(200000) / log1p(450000) from ['ev_dd4002c0e8a657153adc2858'] |
| competition | evidence | 0.900 | 0.100 | 0.15 | 0.015 | `ev_dd4002c0e8a657153adc2858` | competition 0.900 from ['ev_dd4002c0e8a657153adc2858'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.15 | 0.075 | `ev_07796cf1a16e407bfe617b36` | judgment ev_07796cf1a16e407bfe617b36: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 9. vacuum insulation: 0.577

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.500 | 0.500 | 0.35 | 0.175 | `ev_c3800fb0b151ce7558528a5a` | judgment ev_c3800fb0b151ce7558528a5a: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| demand | evidence | 0.562 | 0.562 | 0.25 | 0.140 | `ev_0e00bac0c3e1419e9571ec44` | log1p(1500) / log1p(450000) from ['ev_0e00bac0c3e1419e9571ec44'] |
| competition | evidence | 0.200 | 0.800 | 0.15 | 0.120 | `ev_0e00bac0c3e1419e9571ec44` | competition 0.200 from ['ev_0e00bac0c3e1419e9571ec44'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.15 | 0.075 | `ev_54d4a1230a98eeec0b257f34` | judgment ev_54d4a1230a98eeec0b257f34: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 10. bpa free: 0.569

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.500 | 0.500 | 0.35 | 0.175 | `ev_c02e670000ea68340f1a7255` | judgment ev_c02e670000ea68340f1a7255: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| demand | evidence | 0.708 | 0.708 | 0.25 | 0.177 | `ev_b7056b1e3800ee4bf7ec6a63` | log1p(10000) / log1p(450000) from ['ev_b7056b1e3800ee4bf7ec6a63'] |
| competition | evidence | 0.500 | 0.500 | 0.15 | 0.075 | `ev_b7056b1e3800ee4bf7ec6a63` | competition 0.500 from ['ev_b7056b1e3800ee4bf7ec6a63'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.15 | 0.075 | `ev_d90852da77b2da7b5a188c76` | judgment ev_d90852da77b2da7b5a188c76: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| competitor_coverage | evidence | 0.667 | 0.667 | 0.10 | 0.067 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 2/3 competitor listings contain the phrase |

### 11. insulated water bottle with straw: 0.525

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.400 | 0.400 | 0.35 | 0.140 | `ev_75a3b8e0e07aacd23f114fec` | judgment ev_75a3b8e0e07aacd23f114fec: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.8: The product has a lid, not a straw. |
| demand | evidence | 0.778 | 0.778 | 0.25 | 0.194 | `ev_8ea1aeea6e6605cb8cfd5c17` | log1p(25000) / log1p(450000) from ['ev_8ea1aeea6e6605cb8cfd5c17'] |
| competition | evidence | 0.450 | 0.550 | 0.15 | 0.083 | `ev_8ea1aeea6e6605cb8cfd5c17` | competition 0.450 from ['ev_8ea1aeea6e6605cb8cfd5c17'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.15 | 0.075 | `ev_4b7f3c06b22cdac8dcc99d0c` | judgment ev_4b7f3c06b22cdac8dcc99d0c: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| competitor_coverage | evidence | 0.333 | 0.333 | 0.10 | 0.033 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 1/3 competitor listings contain the phrase |

### 12. insulated water bottle stainless steel: 0.520

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.500 | 0.500 | 0.35 | 0.175 | `ev_0825b53905b6cffd6669fcd2` | judgment ev_0825b53905b6cffd6669fcd2: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| demand | evidence | 0.722 | 0.722 | 0.25 | 0.180 | `ev_392a3ce9a9c419a6ab594166` | log1p(12000) / log1p(450000) from ['ev_392a3ce9a9c419a6ab594166'] |
| competition | evidence | 0.400 | 0.600 | 0.15 | 0.090 | `ev_392a3ce9a9c419a6ab594166` | competition 0.400 from ['ev_392a3ce9a9c419a6ab594166'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.15 | 0.075 | `ev_7cc6d2c32619342f4caab6fb` | judgment ev_7cc6d2c32619342f4caab6fb: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 0/3 competitor listings contain the phrase |

### 13. water bottles for kids: 0.506

Family phrases: `water bottles for kids`, `kids water bottle`

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.350 | 0.350 | 0.35 | 0.122 | `ev_c77116e2af9c468a9062f287` | judgment ev_c77116e2af9c468a9062f287: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.7: Not positioned as a kids' bottle. |
| demand | evidence | 0.881 | 0.881 | 0.25 | 0.220 | `ev_a46145f25f3cf0cd1befe0fb`, `ev_5cd7fadd0c663aa3e7aad93b` | log1p(60000 + 35000 = 95000) / log1p(450000) from ['ev_a46145f25f3cf0cd1befe0fb', 'ev_5cd7fadd0c663aa3e7aad93b'] |
| competition | evidence | 0.632 | 0.368 | 0.15 | 0.055 | `ev_a46145f25f3cf0cd1befe0fb`, `ev_5cd7fadd0c663aa3e7aad93b` | volume-weighted mean 0.632 from ['ev_a46145f25f3cf0cd1befe0fb', 'ev_5cd7fadd0c663aa3e7aad93b'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.15 | 0.075 | `ev_a058c30496b717b37a7a22fb` | judgment ev_a058c30496b717b37a7a22fb: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| competitor_coverage | evidence | 0.333 | 0.333 | 0.10 | 0.033 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 1/3 competitor listings contain any of 2 member phrases |

### 14. water bottle with straw: 0.477

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.300 | 0.300 | 0.35 | 0.105 | `ev_ad87b3907d07ccb61840fedb` | judgment ev_ad87b3907d07ccb61840fedb: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.8: Straw bottles are a different variant. |
| demand | evidence | 0.876 | 0.876 | 0.25 | 0.219 | `ev_8cd644a1a6f2b00053780bc1` | log1p(90000) / log1p(450000) from ['ev_8cd644a1a6f2b00053780bc1'] |
| competition | evidence | 0.700 | 0.300 | 0.15 | 0.045 | `ev_8cd644a1a6f2b00053780bc1` | competition 0.700 from ['ev_8cd644a1a6f2b00053780bc1'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.15 | 0.075 | `ev_e432bd40d33fa6a51a65d664` | judgment ev_e432bd40d33fa6a51a65d664: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| competitor_coverage | evidence | 0.333 | 0.333 | 0.10 | 0.033 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 1/3 competitor listings contain the phrase |

### 15. hydra water bottle: 0.443

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.300 | 0.300 | 0.35 | 0.105 | `ev_e655b5a410e6db64486a784e` | judgment ev_e655b5a410e6db64486a784e: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.8: A competitor's brand query. |
| demand | evidence | 0.690 | 0.690 | 0.25 | 0.173 | `ev_56f3efff8b83587b4237e9d0` | log1p(8000) / log1p(450000) from ['ev_56f3efff8b83587b4237e9d0'] |
| competition | evidence | 0.400 | 0.600 | 0.15 | 0.090 | `ev_56f3efff8b83587b4237e9d0` | competition 0.400 from ['ev_56f3efff8b83587b4237e9d0'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.15 | 0.075 | `ev_9286b3d79295b066da1605eb` | judgment ev_9286b3d79295b066da1605eb: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.6: Synthetic default: no scripted answer. |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 0/3 competitor listings contain the phrase |

### 16. bottle water: 0.367

Intent label (judgment): transactional

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.050 | 0.050 | 0.35 | 0.017 | `ev_8cf83f511bf6a629c93a77ab` | judgment ev_8cf83f511bf6a629c93a77ab: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.95: Bottled drinking water, not a container. |
| demand | evidence | 0.857 | 0.857 | 0.25 | 0.214 | `ev_b0f86f3f003846b0a5944e1b` | log1p(70000) / log1p(450000) from ['ev_b0f86f3f003846b0a5944e1b'] |
| competition | evidence | 0.900 | 0.100 | 0.15 | 0.015 | `ev_b0f86f3f003846b0a5944e1b` | competition 0.900 from ['ev_b0f86f3f003846b0a5944e1b'], scored as 1 - value |
| intent | judgment | 0.800 | 0.800 | 0.15 | 0.120 | `ev_166ecafdabd9e6c483d9d206` | judgment ev_166ecafdabd9e6c483d9d206: synthetic-scripted-v1 / judgment_batch-v1, confidence 0.8: Buying bottled water. |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5` (+1 more) | 0/3 competitor listings contain the phrase |

## Unscored keywords (missing evidence)

- insulated water: demand: missing: no keyword_metric evidence; competition: missing: no keyword_metric evidence
- wall vacuum: demand: missing: no keyword_metric evidence; competition: missing: no keyword_metric evidence
- wall vacuum insulation: demand: missing: no keyword_metric evidence; competition: missing: no keyword_metric evidence

## Semantic judgments

53 valid judgments: entity 19, equivalence 2, intent 16, relevance 16. Models/prompts: rules:own_title_words (deterministic-v1); synthetic-scripted-v1 (judgment_batch-v1).
- Entity flag: `hydra water bottle` is a brand reference (Hydra); kept out of the backend and of listing recommendations. Judgment `ev_c10614473f15fb742c5d3403`

## Semantic usage

5 API calls (0 live, 5 replayed; 3 fast tier, 2 strong tier, 1 items escalated) supplied 48 model judgments. Answered without a model call: 0 cache hits, 0 human, 5 deterministic; 6 not needed.

Planned: expected $0.0274 ($0.0006 per judgment), worst case $0.0959 (estimates from the call plans, pricing as of 2026-09-25).
Measured cost: none (no live calls in this run).
Limits: max live calls none, max cost none.

| Provider / model | Records | Live | Replayed | Fast / strong calls | Judgments | Cache hits | Input tok | Output tok | Est. cost | Failures |
|---|---|---|---|---|---|---|---|---|---|---|
| anthropic / synthetic-scripted-v1 | 5 | 0 | 5 | 3 / 2 | 49 | 0 | 7561 | 2239 | - | none |

### Semantic call plan

| Stage | Requested | Human | Rules | Skipped | Cache | Live | Calls (planned / expected / worst) | Expected cost | Worst-case cost |
|---|---|---|---|---|---|---|---|---|---|
| review_themes | 1 | 0 | 0 | 0 | 0 | 1 | 1 / 1 / 1 | $0.0038 | $0.0167 |
| equivalence_judgments | 2 | 0 | 0 | 0 | 0 | 2 | 1 / 1 / 2 | $0.0024 | $0.0092 |
| keyword_judgments | 57 | 0 | 5 | 6 | 0 | 46 | 2 / 3 / 3 | $0.0212 | $0.0700 |
| **total** | 60 | 0 | 5 | 6 | 0 | 49 | 4 / 5 / 6 | $0.0274 | $0.0959 |

| Stage | Call | Tier / model | Items | Types | max_tokens | Est. input tok | Expected | Worst case |
|---|---|---|---|---|---|---|---|---|
| review_themes | batch | strong / claude-sonnet-5-5 | 1 | review_themes 1 | 1528 | 725 | $0.0038 | $0.0167 |
| equivalence_judgments | batch | fast / claude-haiku-4-5 | 2 | equivalence 2 | 350 | 1303 | $0.0020 | $0.0031 |
| equivalence_judgments | reserve | strong / claude-sonnet-5-5 | 2 | equivalence 2 | 350 | 1316 | $0.0040 | $0.0061 |
| keyword_judgments | batch | fast / claude-haiku-4-5 | 23 | entity 7, intent 8, relevance 8 | 3974 | 2140 | $0.0090 | $0.0220 |
| keyword_judgments | batch | fast / claude-haiku-4-5 | 23 | entity 7, intent 8, relevance 8 | 3974 | 2119 | $0.0089 | $0.0220 |
| keyword_judgments | reserve | strong / claude-sonnet-5-5 | 12 | entity 12 | 2256 | 1721 | $0.0110 | $0.0260 |

- review_themes: 8 reviews in one call
- equivalence_judgments: escalation reserve: up to 12 of 2 live items (expected 0.2 at rate 0.1)
- keyword_judgments: escalation reserve: up to 12 of 46 live items (expected 4.6 at rate 0.1)

## Review themes

Repeated means at least 2 supporting reviews.

### Repeated positive themes

- **keeps drinks cold all day**: 3 reviews across B0COMP0001, B0COMP0002, B0COMP0003. Evidence: `ev_f977e3e736cdfecc500744a9`, `ev_56e0e6b87e00d35b57833510`, `ev_0ad3e9d63792c0fe395580c3`, `ev_fea2f2c7494d2bee121484ff`

### Repeated complaints

- **lid leaks**: 3 reviews across B0COMP0001, B0COMP0002. Evidence: `ev_f05c815ca672eec620ca5f28`, `ev_8b2c44d94e33b1a838d0e989`, `ev_6ab5665930a5bff6f779e795`, `ev_9ab08f55fed160042f1a57e5`

### Possible listing opportunities

- Buyers of 2 competitor product(s) repeatedly report 'lid leaks' (3 reviews). Address it in the listing only if the product genuinely avoids this problem. ProductInput lists related feature(s): Leak proof lid with carry loop. Evidence: `ev_f05c815ca672eec620ca5f28`, `ev_8b2c44d94e33b1a838d0e989`, `ev_6ab5665930a5bff6f779e795`, `ev_9ab08f55fed160042f1a57e5`
- Buyers of 3 competitor product(s) repeatedly value 'keeps drinks cold all day' (3 reviews). If the product offers this, make sure the listing says so. ProductInput lists related feature(s): Double wall vacuum insulation keeps drinks cold for 24 hours. Evidence: `ev_f977e3e736cdfecc500744a9`, `ev_56e0e6b87e00d35b57833510`, `ev_0ad3e9d63792c0fe395580c3`, `ev_fea2f2c7494d2bee121484ff`

Other themes (not repeated, or mixed/neutral): heavy (negative, 1)

## Recommendations

- **keyword_gap** `insulated water bottle`: Ranked #1 (score 0.793) but none of its 2 family phrases appears in any weighted field. Consider: title, item_highlights, bullets, description. Family variants: water bottle insulated. Packed by proposal `prop_205572e03aa7c4deba30062d`. Evidence: `ev_03696b6c4a2af8d1cacf3837`, `ev_15dcaed51f61e9a6b1d41b04`, `ev_55405880b83009c2c09d4cf3`, `ev_65bd2a73cef4e176a078362d` (+3 more)
- **placement_upgrade** `leak proof`: Ranked #3 (score 0.715) but found only in bullets (placement 0.60). Consider: title, item_highlights. Evidence: `ev_cf7e3fc8b95a8a07a66eb764`, `ev_fad466f336253d1d8ca2237d`, `ev_7022ed0ac53723496f8dc83f`, `ev_35f6d219e7c49ae7d271b453` (+2 more)
- **keyword_gap** `double wall vacuum`: Ranked #4 (score 0.695) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Packed by proposal `prop_205572e03aa7c4deba30062d`. Evidence: `ev_24c48a691532da4532e6c514`, `ev_9d5250bbe438bc5c61e9a908`, `ev_0c35a921b7b572008717b040`, `ev_35f6d219e7c49ae7d271b453` (+2 more)
- **keyword_gap** `straw lid`: Ranked #6 (score 0.599) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Packed by proposal `prop_205572e03aa7c4deba30062d`. Evidence: `ev_58b1375bc0fd4bc0c9b8e7a7`, `ev_bbc9eb0091469ac753904ecd`, `ev_448bd96196252660b53c4149`, `ev_35f6d219e7c49ae7d271b453` (+2 more)
- **keyword_gap** `double wall`: Ranked #7 (score 0.588) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Evidence: `ev_7b33e06554be82389269370c`, `ev_ef542322b00eac38e76bd170`, `ev_14cf9255cf7a65d5eccf1a84`, `ev_35f6d219e7c49ae7d271b453` (+2 more)
- **keyword_gap** `vacuum insulation`: Ranked #9 (score 0.577) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Packed by proposal `prop_205572e03aa7c4deba30062d`. Evidence: `ev_c3800fb0b151ce7558528a5a`, `ev_0e00bac0c3e1419e9571ec44`, `ev_54d4a1230a98eeec0b257f34`, `ev_35f6d219e7c49ae7d271b453` (+2 more)
- **keyword_gap** `bpa free`: Ranked #10 (score 0.569) but the exact phrase appears in no weighted field. Consider: title, item_highlights, bullets, description. Packed by proposal `prop_205572e03aa7c4deba30062d`. Evidence: `ev_c02e670000ea68340f1a7255`, `ev_b7056b1e3800ee4bf7ec6a63`, `ev_d90852da77b2da7b5a188c76`, `ev_35f6d219e7c49ae7d271b453` (+2 more)

## Proposals

### `prop_205572e03aa7c4deba30062d`: search_terms (evidence)

Packs 6 of 16 ranked keywords, best first, into search_terms (76/249 bytes). Excluded: 7 duplicate, 1 entity_flag, 25 in_visible_listing, 3 stopword. Skips 2 redundant family member(s) sharing their canonical's words: water bottle insulated, kids water bottle. Retains current unscored content: flask, gym, hiking.

Proposed value: `insulated double wall vacuum straw insulation bpa free kids flask gym hiking`

Validation: **VALID**

Evidence: `ev_03696b6c4a2af8d1cacf3837`, `ev_15dcaed51f61e9a6b1d41b04`, `ev_55405880b83009c2c09d4cf3`, `ev_65bd2a73cef4e176a078362d`, `ev_35f6d219e7c49ae7d271b453`, `ev_fa63e88a13aaa2fae13c6ac5`, `ev_eb2efabff59698fdccb240fd`, `ev_24c48a691532da4532e6c514` (+15 more)
