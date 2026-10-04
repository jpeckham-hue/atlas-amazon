# Research report: The Quiet Harbor

- Run: `run-book-001` at 2026-10-03T09:00:00+00:00 (atlas 0.10.0)
- Recipe: `book` 0.2.0 (amazon-base > book), marketplace US
- Seeds (seed_keywords attribute): cozy mystery, small town mystery
- Providers: catalog=fixture, keywords=fixture, suggestions=fixture, reviews=fixture, review_themes=fixture, judgments=fixture, human_judgments=human
- Keyword families: on
- Evidence fingerprint: `4b90ff14975f2985`

## Research tasks

| Priority | Task | Status | New / reused | Note |
|---|---|---|---|---|
| comparable_titles | competitor_catalog | executed | 3 / 0 | requested 3 competitor ASINs |
| reader_review_themes | competitor_reviews | executed | 11 / 0 | reviews for 4 ASINs; 4 review themes from 7 stored reviews |
| browse_categories | - | unsupported | 0 / 0 | no offline research task implements this priority yet |
| search_term_demand | search_demand | executed | 16 / 0 | suggestions for 2 seeds; metrics requested for 14 candidates |
| series_and_format_signals | - | unsupported | 0 / 0 | no offline research task implements this priority yet |
| semantic | equivalence_judgments | executed | 1 / 0 | 1 requested, 1 valid model judgments |
| semantic | keyword_judgments | executed | 21 / 0 | 39 requested, 16 valid model judgments, 3 deterministic, 2 human, 18 unanswered (fallbacks apply) |

## Evidence summary

52 records. By kind: autocomplete_suggestion 2, catalog_item 3, judgment 22, keyword_metric 14, review_sample 7, review_theme 4.

- Missing, asins without reviews: B0BOOK0001

## Current listing audit: passed

- **warning** `keyword_avoid_terms`: prohibited terms: ['book'] [kdp-keywords, verified]

## Keyword families

- **cozy mystery books** (`fam_cd560c743d8a1ecf`, canonical: highest search volume among members (33000)): `cozy mystery books`, `mystery books cozy`
  - `cozy mystery books` ~ `mystery books cozy` [judgment]: equivalence judgment (fixture-judge-1, equivalence-fixture-v1, confidence 0.85): Same request: cozy mystery books, with the genre word moved. Evidence: `ev_3550bae6d636219dd85408c9`

## Ranked keywords

| # | Keyword (family) | Score | Relevance | Demand | Competition (inv.) | Intent | Competitor coverage |
|---|---|---|---|---|---|---|---|
| 1 | cozy mystery | 0.758 | 0.380 J | 0.188 | 0.020 | 0.070 J | 0.100 |
| 2 | amateur sleuth | 0.756 | 0.320 J | 0.146 | 0.140 | 0.050 H | 0.100 |
| 3 | small town murder mystery | 0.687 | 0.320 J | 0.137 | 0.130 | 0.100 H | 0.000 |
| 4 | cozy mystery series | 0.666 | 0.360 R | 0.171 | 0.060 | 0.075 H | 0.000 |
| 5 | small town mystery books | 0.654 | 0.320 J | 0.134 | 0.120 | 0.080 J | 0.000 |
| 6 | cozy mystery books (+1 variant) | 0.651 | 0.360 J | 0.179 | 0.032 | 0.080 J | 0.000 |
| 7 | small town mystery | 0.646 | 0.340 J | 0.156 | 0.080 | 0.070 J | 0.000 |
| 8 | cozy mystery kindle unlimited | 0.604 | 0.240 J | 0.164 | 0.100 | 0.100 H | 0.000 |
| 9 | agatha christie cozy mystery | 0.511 | 0.160 J | 0.151 | 0.100 | 0.100 H | 0.000 |
| 10 | mystery books | 0.494 | 0.240 J | 0.200 | 0.004 | 0.050 J | 0.000 |
| 11 | small town | 0.473 | 0.120 J | 0.193 | 0.010 | 0.050 H | 0.100 |
| 12 | cozy mystery with cats | 0.455 | 0.040 R | 0.142 | 0.140 | 0.100 H | 0.033 |
| 13 | harbor town | 0.377 | 0.080 J | 0.067 | 0.180 | 0.050 H | 0.000 |

Cells show weighted contributions. J = model judgment; R = human reviewer judgment (overrides the model); H = heuristic placeholder (no evidence); unmarked = measured evidence.

## Signal breakdown

### 1. cozy mystery: 0.758

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.950 | 0.950 | 0.40 | 0.380 | `ev_b53f4bfc4e62c05ff205452e` | judgment ev_b53f4bfc4e62c05ff205452e: fixture-judge-1 / relevance-fixture-v1, confidence 0.9: The book's genre. |
| demand | evidence | 0.941 | 0.941 | 0.20 | 0.188 | `ev_032145039c2e06a55e944a02` | log1p(60000) / log1p(120000) from ['ev_032145039c2e06a55e944a02'] |
| competition | evidence | 0.900 | 0.100 | 0.20 | 0.020 | `ev_032145039c2e06a55e944a02` | competition 0.900 from ['ev_032145039c2e06a55e944a02'], scored as 1 - value |
| intent | judgment | 0.700 | 0.700 | 0.10 | 0.070 | `ev_5ba3a4fc12ef42bbc77b7781` | judgment ev_5ba3a4fc12ef42bbc77b7781: fixture-judge-1 / intent-fixture-v1, confidence 0.8: Genre browsing. |
| competitor_coverage | evidence | 1.000 | 1.000 | 0.10 | 0.100 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 3/3 competitor listings contain the phrase |

### 2. amateur sleuth: 0.756

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.800 | 0.800 | 0.40 | 0.320 | `ev_4b0f4f669ae9731858973b48` | judgment ev_4b0f4f669ae9731858973b48: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: The protagonist is an amateur sleuth. |
| demand | evidence | 0.728 | 0.728 | 0.20 | 0.146 | `ev_517ce780c6a55e5b4ae27135` | log1p(5000) / log1p(120000) from ['ev_517ce780c6a55e5b4ae27135'] |
| competition | evidence | 0.300 | 0.700 | 0.20 | 0.140 | `ev_517ce780c6a55e5b4ae27135` | competition 0.300 from ['ev_517ce780c6a55e5b4ae27135'], scored as 1 - value |
| intent | heuristic | 0.500 | 0.500 | 0.10 | 0.050 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | evidence | 1.000 | 1.000 | 0.10 | 0.100 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 3/3 competitor listings contain the phrase |

### 3. small town murder mystery: 0.687

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.800 | 0.800 | 0.40 | 0.320 | `ev_206769255b32491984e0ccc5` | judgment ev_206769255b32491984e0ccc5: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: Accurate subgenre description. |
| demand | evidence | 0.685 | 0.685 | 0.20 | 0.137 | `ev_f1ac8667c062fc9bd3c6f8da` | log1p(3000) / log1p(120000) from ['ev_f1ac8667c062fc9bd3c6f8da'] |
| competition | evidence | 0.350 | 0.650 | 0.20 | 0.130 | `ev_f1ac8667c062fc9bd3c6f8da` | competition 0.350 from ['ev_f1ac8667c062fc9bd3c6f8da'], scored as 1 - value |
| intent | heuristic | 1.000 | 1.000 | 0.10 | 0.100 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 4. cozy mystery series: 0.666

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | human | 0.900 | 0.900 | 0.40 | 0.360 | `ev_35b0f5686c9e670ce7a2d689` | judgment ev_35b0f5686c9e670ce7a2d689: human:editor / human-review-v1, confidence 1: The author confirmed this is book 1 of the Harbor Mysteries series. |
| demand | evidence | 0.855 | 0.855 | 0.20 | 0.171 | `ev_4d5f1b62831d4d8a5988cfd2` | log1p(22000) / log1p(120000) from ['ev_4d5f1b62831d4d8a5988cfd2'] |
| competition | evidence | 0.700 | 0.300 | 0.20 | 0.060 | `ev_4d5f1b62831d4d8a5988cfd2` | competition 0.700 from ['ev_4d5f1b62831d4d8a5988cfd2'], scored as 1 - value |
| intent | heuristic | 0.750 | 0.750 | 0.10 | 0.075 | none | heuristic: specificity proxy min(1, 3 words / 4) |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 5. small town mystery books: 0.654

Intent label (judgment): transactional

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.800 | 0.800 | 0.40 | 0.320 | `ev_89f53971bfa1b1b5e360812e` | judgment ev_89f53971bfa1b1b5e360812e: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: Accurate subgenre description. |
| demand | evidence | 0.669 | 0.669 | 0.20 | 0.134 | `ev_f6f5d59a7552836012746768` | log1p(2500) / log1p(120000) from ['ev_f6f5d59a7552836012746768'] |
| competition | evidence | 0.400 | 0.600 | 0.20 | 0.120 | `ev_f6f5d59a7552836012746768` | competition 0.400 from ['ev_f6f5d59a7552836012746768'], scored as 1 - value |
| intent | judgment | 0.800 | 0.800 | 0.10 | 0.080 | `ev_fc20c6d2cb59b332dad0bbc0` | judgment ev_fc20c6d2cb59b332dad0bbc0: rules:format_word_shopping / deterministic-v1, confidence 1: A qualified subgenre with the format word 'book' as its head is a search for products in that subgenre, not genre browsing. |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 6. cozy mystery books: 0.651

Family phrases: `cozy mystery books`, `mystery books cozy`

Intent label (judgment): transactional

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.900 | 0.900 | 0.40 | 0.360 | `ev_ae9c55ed731350edcbe43398` | judgment ev_ae9c55ed731350edcbe43398: fixture-judge-1 / relevance-fixture-v1, confidence 0.85: The genre, in plural form. |
| demand | evidence | 0.893 | 0.893 | 0.20 | 0.179 | `ev_ab17863b10dfe2ce5937850f`, `ev_e40e07f72b8611c03eff23bf` | log1p(33000 + 1200 = 34200) / log1p(120000) from ['ev_ab17863b10dfe2ce5937850f', 'ev_e40e07f72b8611c03eff23bf'] |
| competition | evidence | 0.838 | 0.162 | 0.20 | 0.032 | `ev_ab17863b10dfe2ce5937850f`, `ev_e40e07f72b8611c03eff23bf` | volume-weighted mean 0.838 from ['ev_ab17863b10dfe2ce5937850f', 'ev_e40e07f72b8611c03eff23bf'], scored as 1 - value |
| intent | judgment | 0.800 | 0.800 | 0.10 | 0.080 | `ev_43abd0428feb82fe9b29fed8` | judgment ev_43abd0428feb82fe9b29fed8: rules:format_word_shopping / deterministic-v1, confidence 1: A qualified subgenre with the format word 'book' as its head is a search for products in that subgenre, not genre browsing. |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain any of 2 member phrases |

### 7. small town mystery: 0.646

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.850 | 0.850 | 0.40 | 0.340 | `ev_d470380a6465af0557af06ce` | judgment ev_d470380a6465af0557af06ce: fixture-judge-1 / relevance-fixture-v1, confidence 0.85: Genre plus the book's setting. |
| demand | evidence | 0.779 | 0.779 | 0.20 | 0.156 | `ev_7ca4e84cf849746a7781c6cc` | log1p(9000) / log1p(120000) from ['ev_7ca4e84cf849746a7781c6cc'] |
| competition | evidence | 0.600 | 0.400 | 0.20 | 0.080 | `ev_7ca4e84cf849746a7781c6cc` | competition 0.600 from ['ev_7ca4e84cf849746a7781c6cc'], scored as 1 - value |
| intent | judgment | 0.700 | 0.700 | 0.10 | 0.070 | `ev_f50f94324d5fba206de5cb4b` | judgment ev_f50f94324d5fba206de5cb4b: fixture-judge-1 / intent-fixture-v1, confidence 0.75: Subgenre browsing. |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 8. cozy mystery kindle unlimited: 0.604

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.600 | 0.600 | 0.40 | 0.240 | `ev_5208d048eed04cb6b052f582` | judgment ev_5208d048eed04cb6b052f582: fixture-judge-1 / relevance-fixture-v1, confidence 0.7: Genre plus a program name. |
| demand | evidence | 0.822 | 0.822 | 0.20 | 0.164 | `ev_ad1bc7fbd35e84bc8c65c180` | log1p(15000) / log1p(120000) from ['ev_ad1bc7fbd35e84bc8c65c180'] |
| competition | evidence | 0.500 | 0.500 | 0.20 | 0.100 | `ev_ad1bc7fbd35e84bc8c65c180` | competition 0.500 from ['ev_ad1bc7fbd35e84bc8c65c180'], scored as 1 - value |
| intent | heuristic | 1.000 | 1.000 | 0.10 | 0.100 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 9. agatha christie cozy mystery: 0.511

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.400 | 0.400 | 0.40 | 0.160 | `ev_f907512d7afdb08fa7ff93ec` | judgment ev_f907512d7afdb08fa7ff93ec: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: Names another author. |
| demand | evidence | 0.757 | 0.757 | 0.20 | 0.151 | `ev_8e815240ec0a86eb763b2350` | log1p(7000) / log1p(120000) from ['ev_8e815240ec0a86eb763b2350'] |
| competition | evidence | 0.500 | 0.500 | 0.20 | 0.100 | `ev_8e815240ec0a86eb763b2350` | competition 0.500 from ['ev_8e815240ec0a86eb763b2350'], scored as 1 - value |
| intent | heuristic | 1.000 | 1.000 | 0.10 | 0.100 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 10. mystery books: 0.494

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.600 | 0.600 | 0.40 | 0.240 | `ev_8c7c62beac705133307f8261` | judgment ev_8c7c62beac705133307f8261: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: Broad parent category. |
| demand | evidence | 1.000 | 1.000 | 0.20 | 0.200 | `ev_a7d3a0538d12a3cf522e368e` | log1p(120000) / log1p(120000) from ['ev_a7d3a0538d12a3cf522e368e'] |
| competition | evidence | 0.980 | 0.020 | 0.20 | 0.004 | `ev_a7d3a0538d12a3cf522e368e` | competition 0.980 from ['ev_a7d3a0538d12a3cf522e368e'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.10 | 0.050 | `ev_80fd300ee1cddab3f41f7cf0` | judgment ev_80fd300ee1cddab3f41f7cf0: fixture-judge-1 / intent-fixture-v1, confidence 0.8: Broad browsing. |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 11. small town: 0.473

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.300 | 0.300 | 0.40 | 0.120 | `ev_f2290096163f13685ba36934` | judgment ev_f2290096163f13685ba36934: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: A setting word; on its own not a book search. |
| demand | evidence | 0.965 | 0.965 | 0.20 | 0.193 | `ev_08e7fd0a971ef89dfd019482` | log1p(80000) / log1p(120000) from ['ev_08e7fd0a971ef89dfd019482'] |
| competition | evidence | 0.950 | 0.050 | 0.20 | 0.010 | `ev_08e7fd0a971ef89dfd019482` | competition 0.950 from ['ev_08e7fd0a971ef89dfd019482'], scored as 1 - value |
| intent | heuristic | 0.500 | 0.500 | 0.10 | 0.050 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | evidence | 1.000 | 1.000 | 0.10 | 0.100 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 3/3 competitor listings contain the phrase |

### 12. cozy mystery with cats: 0.455

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | human | 0.100 | 0.100 | 0.40 | 0.040 | `ev_0c089f9ffe969d54a2e0b2f7` | judgment ev_0c089f9ffe969d54a2e0b2f7: human:editor / human-review-v1, confidence 1: Checked against the manuscript: no cat characters appear. |
| demand | evidence | 0.709 | 0.709 | 0.20 | 0.142 | `ev_55ffac87c8a1334c175608c8` | log1p(4000) / log1p(120000) from ['ev_55ffac87c8a1334c175608c8'] |
| competition | evidence | 0.300 | 0.700 | 0.20 | 0.140 | `ev_55ffac87c8a1334c175608c8` | competition 0.300 from ['ev_55ffac87c8a1334c175608c8'], scored as 1 - value |
| intent | heuristic | 1.000 | 1.000 | 0.10 | 0.100 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | evidence | 0.333 | 0.333 | 0.10 | 0.033 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 1/3 competitor listings contain the phrase |

### 13. harbor town: 0.377

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.200 | 0.200 | 0.40 | 0.080 | `ev_a343a378c629e7382b2595b6` | judgment ev_a343a378c629e7382b2595b6: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: Echoes the title, but readers don't search it. |
| demand | evidence | 0.336 | 0.336 | 0.20 | 0.067 | `ev_41014cb601f7405ebe1aae96` | log1p(50) / log1p(120000) from ['ev_41014cb601f7405ebe1aae96'] |
| competition | evidence | 0.100 | 0.900 | 0.20 | 0.180 | `ev_41014cb601f7405ebe1aae96` | competition 0.100 from ['ev_41014cb601f7405ebe1aae96'], scored as 1 - value |
| intent | heuristic | 0.500 | 0.500 | 0.10 | 0.050 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

## Semantic judgments

22 valid judgments: entity 3, equivalence 1, intent 5, relevance 13. Models/prompts: fixture-judge-1 (entity-fixture-v1); fixture-judge-1 (equivalence-fixture-v1); fixture-judge-1 (intent-fixture-v1); fixture-judge-1 (relevance-fixture-v1); human:editor (human-review-v1); rules:format_word_shopping (deterministic-v1); rules:recipe_known_entity (deterministic-v1).
- Entity flag: `cozy mystery kindle unlimited` is a trademark reference (kindle unlimited); kept out of the backend and of listing recommendations. Judgment `ev_a9df96e332a9e9cd6e816870`
- Entity flag: `agatha christie cozy mystery` is a author reference (Agatha Christie); kept out of the backend and of listing recommendations. Judgment `ev_e5f659d5c1d1c354f208efd1`

### Human overrides

| Type | Subject | Model judgment | Human judgment | Used |
|---|---|---|---|---|
| relevance | cozy mystery series | not asked (answered by a human before any model call) | {'score': 0.9} (human:editor): The author confirmed this is book 1 of the Harbor Mysteries series. `ev_35b0f5686c9e670ce7a2d689` | human `ev_35b0f5686c9e670ce7a2d689` |
| relevance | cozy mystery with cats | not asked (answered by a human before any model call) | {'score': 0.1} (human:editor): Checked against the manuscript: no cat characters appear. `ev_0c089f9ffe969d54a2e0b2f7` | human `ev_0c089f9ffe969d54a2e0b2f7` |

## Review themes

Repeated means at least 2 supporting reviews.

### Repeated positive themes

- **clean read (no gore or swearing)**: 3 reviews across B0BOOKC001, B0BOOKC003. Evidence: `ev_6c95568f6a4102161778eac0`, `ev_09b246e29b7aad6f35970784`, `ev_972d8f12445221f0b5d1e3ac`, `ev_f56bedb9664827705a594a16`

### Repeated complaints

- **predictable killer**: 2 reviews across B0BOOKC001, B0BOOKC002. Evidence: `ev_3e6d610d3d15ed73b78b61c2`, `ev_f6cbc3dc926def52ecbda045`, `ev_32f37d65a1f55619687844ce`

### Possible listing opportunities

- Buyers of 2 competitor product(s) repeatedly report 'predictable killer' (2 reviews). Address it in the listing only if the product genuinely avoids this problem. Evidence: `ev_3e6d610d3d15ed73b78b61c2`, `ev_f6cbc3dc926def52ecbda045`, `ev_32f37d65a1f55619687844ce`
- Buyers of 2 competitor product(s) repeatedly value 'clean read (no gore or swearing)' (3 reviews). If the product offers this, make sure the listing says so. ProductInput lists related feature(s): Clean read with no gore or profanity. Evidence: `ev_6c95568f6a4102161778eac0`, `ev_09b246e29b7aad6f35970784`, `ev_972d8f12445221f0b5d1e3ac`, `ev_f56bedb9664827705a594a16`

Other themes (not repeated, or mixed/neutral): cat characters (positive, 1), recipes included (positive, 1)

## Recommendations

- **placement_upgrade** `cozy mystery`: Ranked #1 (score 0.758) but found only in subtitle (placement 0.80). Consider: title. Evidence: `ev_b53f4bfc4e62c05ff205452e`, `ev_032145039c2e06a55e944a02`, `ev_5ba3a4fc12ef42bbc77b7781`, `ev_3930a7a6baddb4c5f22b3787` (+2 more)
- **keyword_gap** `amateur sleuth`: Ranked #2 (score 0.756) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_eb75706a1d9b773adf535ba9`. Evidence: `ev_4b0f4f669ae9731858973b48`, `ev_517ce780c6a55e5b4ae27135`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more)
- **keyword_gap** `small town murder mystery`: Ranked #3 (score 0.687) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_eb75706a1d9b773adf535ba9`. Evidence: `ev_206769255b32491984e0ccc5`, `ev_f1ac8667c062fc9bd3c6f8da`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more)
- **keyword_gap** `cozy mystery series`: Ranked #4 (score 0.666) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_eb75706a1d9b773adf535ba9`. Evidence: `ev_35b0f5686c9e670ce7a2d689`, `ev_4d5f1b62831d4d8a5988cfd2`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more)
- **keyword_gap** `small town mystery books`: Ranked #5 (score 0.654) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Evidence: `ev_89f53971bfa1b1b5e360812e`, `ev_f6f5d59a7552836012746768`, `ev_fc20c6d2cb59b332dad0bbc0`, `ev_3930a7a6baddb4c5f22b3787` (+2 more)
- **keyword_gap** `cozy mystery books`: Ranked #6 (score 0.651) but none of its 2 family phrases appears in any weighted field. Consider: title, subtitle, description. Family variants: mystery books cozy. Evidence: `ev_ae9c55ed731350edcbe43398`, `ev_ab17863b10dfe2ce5937850f`, `ev_e40e07f72b8611c03eff23bf`, `ev_43abd0428feb82fe9b29fed8` (+3 more)
- **keyword_gap** `small town mystery`: Ranked #7 (score 0.646) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_eb75706a1d9b773adf535ba9`. Evidence: `ev_d470380a6465af0557af06ce`, `ev_7ca4e84cf849746a7781c6cc`, `ev_f50f94324d5fba206de5cb4b`, `ev_3930a7a6baddb4c5f22b3787` (+2 more)
- **placement_upgrade** `mystery books`: Ranked #10 (score 0.494) but found only in keywords (placement 0.40). Consider: title, subtitle. Evidence: `ev_8c7c62beac705133307f8261`, `ev_a7d3a0538d12a3cf522e368e`, `ev_80fd300ee1cddab3f41f7cf0`, `ev_3930a7a6baddb4c5f22b3787` (+2 more)

### Market opportunities not supported by the product

Ranked keywords with market evidence that claim something the seller's own product information does not state. They are **not** recommended for listing copy or backend terms; add the feature to the product information first if it is true.

- `cozy mystery with cats` (rank 12, score 0.455): `unsupported_by_product`; no first-party support for 'cat' (checked product_title, subtitle, features, description). Market evidence: `ev_8ade86cc554a59f9e172403c`, `ev_0c089f9ffe969d54a2e0b2f7`, `ev_55ffac87c8a1334c175608c8`, `ev_3930a7a6baddb4c5f22b3787` (+2 more)

## Proposals

### `prop_eb75706a1d9b773adf535ba9`: keywords (evidence)

Packs 6 of 13 ranked keywords, best first, into keywords (3/7 slots). Excluded: 2 entity_flag, 1 in_visible_listing, 3 prohibited_term, 1 unsupported_by_product.

Proposed value: `amateur sleuth small town murder mystery | cozy mystery series small town mystery small town | harbor town`

Validation: **VALID**

Evidence: `ev_4b0f4f669ae9731858973b48`, `ev_517ce780c6a55e5b4ae27135`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e`, `ev_982ab2f536cff485df6b3055`, `ev_206769255b32491984e0ccc5`, `ev_f1ac8667c062fc9bd3c6f8da`, `ev_35b0f5686c9e670ce7a2d689` (+8 more)
