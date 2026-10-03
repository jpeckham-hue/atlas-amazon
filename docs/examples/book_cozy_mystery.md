# Research report: The Quiet Harbor

- Run: `run-book-001` at 2026-10-03T09:00:00+00:00 (atlas 0.4.0a1)
- Recipe: `book` 0.2.0 (amazon-base > book), marketplace US
- Seeds (seed_keywords attribute): cozy mystery, small town mystery
- Providers: catalog=fixture, keywords=fixture, suggestions=fixture, reviews=fixture, review_themes=fixture, judgments=fixture
- Keyword families: on
- Evidence fingerprint: `33424a148b8833e8`

## Research tasks

| Priority | Task | Status | New / reused | Note |
|---|---|---|---|---|
| comparable_titles | competitor_catalog | executed | 3 / 0 | requested 3 competitor ASINs |
| reader_review_themes | competitor_reviews | executed | 11 / 0 | reviews for 4 ASINs; 4 review themes from 7 stored reviews |
| browse_categories | - | unsupported | 0 / 0 | no offline research task implements this priority yet |
| search_term_demand | search_demand | executed | 16 / 0 | suggestions for 2 seeds; metrics requested for 14 candidates |
| series_and_format_signals | - | unsupported | 0 / 0 | no offline research task implements this priority yet |
| semantic | equivalence_judgments | executed | 1 / 0 | 1 requested, 1 valid judgments |
| semantic | keyword_judgments | executed | 20 / 0 | 39 requested, 20 valid judgments, 19 unanswered (fallbacks apply) |

## Evidence summary

51 records. By kind: autocomplete_suggestion 2, catalog_item 3, judgment 21, keyword_metric 14, review_sample 7, review_theme 4.

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
| 4 | small town mystery books | 0.674 | 0.320 J | 0.134 | 0.120 | 0.100 H | 0.000 |
| 5 | cozy mystery books (+1 variant) | 0.656 | 0.360 J | 0.179 | 0.032 | 0.085 J | 0.000 |
| 6 | small town mystery | 0.646 | 0.340 J | 0.156 | 0.080 | 0.070 J | 0.000 |
| 7 | cozy mystery kindle unlimited | 0.604 | 0.240 J | 0.164 | 0.100 | 0.100 H | 0.000 |
| 8 | cozy mystery with cats | 0.535 | 0.120 J | 0.142 | 0.140 | 0.100 H | 0.033 |
| 9 | agatha christie cozy mystery | 0.511 | 0.160 J | 0.151 | 0.100 | 0.100 H | 0.000 |
| 10 | cozy mystery series | 0.506 | 0.200 J | 0.171 | 0.060 | 0.075 H | 0.000 |
| 11 | mystery books | 0.494 | 0.240 J | 0.200 | 0.004 | 0.050 J | 0.000 |
| 12 | small town | 0.473 | 0.120 J | 0.193 | 0.010 | 0.050 H | 0.100 |
| 13 | harbor town | 0.377 | 0.080 J | 0.067 | 0.180 | 0.050 H | 0.000 |

Cells show weighted contributions. J = semantic judgment (evidence-backed); H = heuristic placeholder (no evidence); unmarked = measured evidence.

## Signal breakdown

### 1. cozy mystery: 0.758

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.950 | 0.950 | 0.40 | 0.380 | `ev_7042cf5d56b0d974f4db97fa` | judgment ev_7042cf5d56b0d974f4db97fa: fixture-judge-1 / relevance-fixture-v1, confidence 0.9: The book's genre. |
| demand | evidence | 0.941 | 0.941 | 0.20 | 0.188 | `ev_032145039c2e06a55e944a02` | log1p(60000) / log1p(120000) from ['ev_032145039c2e06a55e944a02'] |
| competition | evidence | 0.900 | 0.100 | 0.20 | 0.020 | `ev_032145039c2e06a55e944a02` | competition 0.900 from ['ev_032145039c2e06a55e944a02'], scored as 1 - value |
| intent | judgment | 0.700 | 0.700 | 0.10 | 0.070 | `ev_8b676afc6e54ac3e2de275fa` | judgment ev_8b676afc6e54ac3e2de275fa: fixture-judge-1 / intent-fixture-v1, confidence 0.8: Genre browsing. |
| competitor_coverage | evidence | 1.000 | 1.000 | 0.10 | 0.100 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 3/3 competitor listings contain the phrase |

### 2. amateur sleuth: 0.756

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.800 | 0.800 | 0.40 | 0.320 | `ev_bb8680325702dc327ef7604b` | judgment ev_bb8680325702dc327ef7604b: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: The protagonist is an amateur sleuth. |
| demand | evidence | 0.728 | 0.728 | 0.20 | 0.146 | `ev_517ce780c6a55e5b4ae27135` | log1p(5000) / log1p(120000) from ['ev_517ce780c6a55e5b4ae27135'] |
| competition | evidence | 0.300 | 0.700 | 0.20 | 0.140 | `ev_517ce780c6a55e5b4ae27135` | competition 0.300 from ['ev_517ce780c6a55e5b4ae27135'], scored as 1 - value |
| intent | heuristic | 0.500 | 0.500 | 0.10 | 0.050 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | evidence | 1.000 | 1.000 | 0.10 | 0.100 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 3/3 competitor listings contain the phrase |

### 3. small town murder mystery: 0.687

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.800 | 0.800 | 0.40 | 0.320 | `ev_94866989109205b68a2acf95` | judgment ev_94866989109205b68a2acf95: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: Accurate subgenre description. |
| demand | evidence | 0.685 | 0.685 | 0.20 | 0.137 | `ev_f1ac8667c062fc9bd3c6f8da` | log1p(3000) / log1p(120000) from ['ev_f1ac8667c062fc9bd3c6f8da'] |
| competition | evidence | 0.350 | 0.650 | 0.20 | 0.130 | `ev_f1ac8667c062fc9bd3c6f8da` | competition 0.350 from ['ev_f1ac8667c062fc9bd3c6f8da'], scored as 1 - value |
| intent | heuristic | 1.000 | 1.000 | 0.10 | 0.100 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 4. small town mystery books: 0.674

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.800 | 0.800 | 0.40 | 0.320 | `ev_ff6e3b8c06891d3ab0929b80` | judgment ev_ff6e3b8c06891d3ab0929b80: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: Accurate subgenre description. |
| demand | evidence | 0.669 | 0.669 | 0.20 | 0.134 | `ev_f6f5d59a7552836012746768` | log1p(2500) / log1p(120000) from ['ev_f6f5d59a7552836012746768'] |
| competition | evidence | 0.400 | 0.600 | 0.20 | 0.120 | `ev_f6f5d59a7552836012746768` | competition 0.400 from ['ev_f6f5d59a7552836012746768'], scored as 1 - value |
| intent | heuristic | 1.000 | 1.000 | 0.10 | 0.100 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 5. cozy mystery books: 0.656

Family phrases: `cozy mystery books`, `mystery books cozy`

Intent label (judgment): transactional

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.900 | 0.900 | 0.40 | 0.360 | `ev_5797890b8641da2711ccc04a` | judgment ev_5797890b8641da2711ccc04a: fixture-judge-1 / relevance-fixture-v1, confidence 0.85: The genre, in plural form. |
| demand | evidence | 0.893 | 0.893 | 0.20 | 0.179 | `ev_ab17863b10dfe2ce5937850f`, `ev_e40e07f72b8611c03eff23bf` | log1p(33000 + 1200 = 34200) / log1p(120000) from ['ev_ab17863b10dfe2ce5937850f', 'ev_e40e07f72b8611c03eff23bf'] |
| competition | evidence | 0.838 | 0.162 | 0.20 | 0.032 | `ev_ab17863b10dfe2ce5937850f`, `ev_e40e07f72b8611c03eff23bf` | volume-weighted mean 0.838 from ['ev_ab17863b10dfe2ce5937850f', 'ev_e40e07f72b8611c03eff23bf'], scored as 1 - value |
| intent | judgment | 0.850 | 0.850 | 0.10 | 0.085 | `ev_5001963761dbd34b342a7792` | judgment ev_5001963761dbd34b342a7792: fixture-judge-1 / intent-fixture-v1, confidence 0.8: Looking for books to buy. |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain any of 2 member phrases |

### 6. small town mystery: 0.646

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.850 | 0.850 | 0.40 | 0.340 | `ev_6e477a32477dac3745277165` | judgment ev_6e477a32477dac3745277165: fixture-judge-1 / relevance-fixture-v1, confidence 0.85: Genre plus the book's setting. |
| demand | evidence | 0.779 | 0.779 | 0.20 | 0.156 | `ev_7ca4e84cf849746a7781c6cc` | log1p(9000) / log1p(120000) from ['ev_7ca4e84cf849746a7781c6cc'] |
| competition | evidence | 0.600 | 0.400 | 0.20 | 0.080 | `ev_7ca4e84cf849746a7781c6cc` | competition 0.600 from ['ev_7ca4e84cf849746a7781c6cc'], scored as 1 - value |
| intent | judgment | 0.700 | 0.700 | 0.10 | 0.070 | `ev_869af14ffaddb642bac7273c` | judgment ev_869af14ffaddb642bac7273c: fixture-judge-1 / intent-fixture-v1, confidence 0.75: Subgenre browsing. |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 7. cozy mystery kindle unlimited: 0.604

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.600 | 0.600 | 0.40 | 0.240 | `ev_b77a700dcd617ffa9d2502f7` | judgment ev_b77a700dcd617ffa9d2502f7: fixture-judge-1 / relevance-fixture-v1, confidence 0.7: Genre plus a program name. |
| demand | evidence | 0.822 | 0.822 | 0.20 | 0.164 | `ev_ad1bc7fbd35e84bc8c65c180` | log1p(15000) / log1p(120000) from ['ev_ad1bc7fbd35e84bc8c65c180'] |
| competition | evidence | 0.500 | 0.500 | 0.20 | 0.100 | `ev_ad1bc7fbd35e84bc8c65c180` | competition 0.500 from ['ev_ad1bc7fbd35e84bc8c65c180'], scored as 1 - value |
| intent | heuristic | 1.000 | 1.000 | 0.10 | 0.100 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 8. cozy mystery with cats: 0.535

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.300 | 0.300 | 0.40 | 0.120 | `ev_d7cb07b78901314f8f48081b` | judgment ev_d7cb07b78901314f8f48081b: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: The book has no cat characters. |
| demand | evidence | 0.709 | 0.709 | 0.20 | 0.142 | `ev_55ffac87c8a1334c175608c8` | log1p(4000) / log1p(120000) from ['ev_55ffac87c8a1334c175608c8'] |
| competition | evidence | 0.300 | 0.700 | 0.20 | 0.140 | `ev_55ffac87c8a1334c175608c8` | competition 0.300 from ['ev_55ffac87c8a1334c175608c8'], scored as 1 - value |
| intent | heuristic | 1.000 | 1.000 | 0.10 | 0.100 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | evidence | 0.333 | 0.333 | 0.10 | 0.033 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 1/3 competitor listings contain the phrase |

### 9. agatha christie cozy mystery: 0.511

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.400 | 0.400 | 0.40 | 0.160 | `ev_892ba344203c6bbeb03b7caa` | judgment ev_892ba344203c6bbeb03b7caa: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: Names another author. |
| demand | evidence | 0.757 | 0.757 | 0.20 | 0.151 | `ev_8e815240ec0a86eb763b2350` | log1p(7000) / log1p(120000) from ['ev_8e815240ec0a86eb763b2350'] |
| competition | evidence | 0.500 | 0.500 | 0.20 | 0.100 | `ev_8e815240ec0a86eb763b2350` | competition 0.500 from ['ev_8e815240ec0a86eb763b2350'], scored as 1 - value |
| intent | heuristic | 1.000 | 1.000 | 0.10 | 0.100 | none | heuristic: specificity proxy min(1, 4 words / 4) |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 10. cozy mystery series: 0.506

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.500 | 0.500 | 0.40 | 0.200 | `ev_328805e5168645f27d41f3ac` | judgment ev_328805e5168645f27d41f3ac: fixture-judge-1 / relevance-fixture-v1, confidence 0.6: Series status is unknown from the input. |
| demand | evidence | 0.855 | 0.855 | 0.20 | 0.171 | `ev_4d5f1b62831d4d8a5988cfd2` | log1p(22000) / log1p(120000) from ['ev_4d5f1b62831d4d8a5988cfd2'] |
| competition | evidence | 0.700 | 0.300 | 0.20 | 0.060 | `ev_4d5f1b62831d4d8a5988cfd2` | competition 0.700 from ['ev_4d5f1b62831d4d8a5988cfd2'], scored as 1 - value |
| intent | heuristic | 0.750 | 0.750 | 0.10 | 0.075 | none | heuristic: specificity proxy min(1, 3 words / 4) |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 11. mystery books: 0.494

Intent label (judgment): commercial_investigation

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.600 | 0.600 | 0.40 | 0.240 | `ev_5cf8a78e6b0d932aff5127c8` | judgment ev_5cf8a78e6b0d932aff5127c8: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: Broad parent category. |
| demand | evidence | 1.000 | 1.000 | 0.20 | 0.200 | `ev_a7d3a0538d12a3cf522e368e` | log1p(120000) / log1p(120000) from ['ev_a7d3a0538d12a3cf522e368e'] |
| competition | evidence | 0.980 | 0.020 | 0.20 | 0.004 | `ev_a7d3a0538d12a3cf522e368e` | competition 0.980 from ['ev_a7d3a0538d12a3cf522e368e'], scored as 1 - value |
| intent | judgment | 0.500 | 0.500 | 0.10 | 0.050 | `ev_eac829f4784299f52a7d58f7` | judgment ev_eac829f4784299f52a7d58f7: fixture-judge-1 / intent-fixture-v1, confidence 0.8: Broad browsing. |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

### 12. small town: 0.473

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.300 | 0.300 | 0.40 | 0.120 | `ev_2c5d1441b8308bf4825ef221` | judgment ev_2c5d1441b8308bf4825ef221: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: A setting word; on its own not a book search. |
| demand | evidence | 0.965 | 0.965 | 0.20 | 0.193 | `ev_08e7fd0a971ef89dfd019482` | log1p(80000) / log1p(120000) from ['ev_08e7fd0a971ef89dfd019482'] |
| competition | evidence | 0.950 | 0.050 | 0.20 | 0.010 | `ev_08e7fd0a971ef89dfd019482` | competition 0.950 from ['ev_08e7fd0a971ef89dfd019482'], scored as 1 - value |
| intent | heuristic | 0.500 | 0.500 | 0.10 | 0.050 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | evidence | 1.000 | 1.000 | 0.10 | 0.100 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 3/3 competitor listings contain the phrase |

### 13. harbor town: 0.377

| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |
|---|---|---|---|---|---|---|---|
| relevance | judgment | 0.200 | 0.200 | 0.40 | 0.080 | `ev_55dcc5add90c9915ce03988d` | judgment ev_55dcc5add90c9915ce03988d: fixture-judge-1 / relevance-fixture-v1, confidence 0.8: Echoes the title, but readers don't search it. |
| demand | evidence | 0.336 | 0.336 | 0.20 | 0.067 | `ev_41014cb601f7405ebe1aae96` | log1p(50) / log1p(120000) from ['ev_41014cb601f7405ebe1aae96'] |
| competition | evidence | 0.100 | 0.900 | 0.20 | 0.180 | `ev_41014cb601f7405ebe1aae96` | competition 0.100 from ['ev_41014cb601f7405ebe1aae96'], scored as 1 - value |
| intent | heuristic | 0.500 | 0.500 | 0.10 | 0.050 | none | heuristic: specificity proxy min(1, 2 words / 4) |
| competitor_coverage | evidence | 0.000 | 0.000 | 0.10 | 0.000 | `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more) | 0/3 competitor listings contain the phrase |

## Semantic judgments

21 valid judgments: entity 3, equivalence 1, intent 4, relevance 13. Models/prompts: fixture-judge-1 (entity-fixture-v1); fixture-judge-1 (equivalence-fixture-v1); fixture-judge-1 (intent-fixture-v1); fixture-judge-1 (relevance-fixture-v1).
- Entity flag: `cozy mystery kindle unlimited` is a trademark reference (Kindle Unlimited); kept out of the backend and of listing recommendations. Judgment `ev_6d7fd4abee216fb162eba157`
- Entity flag: `agatha christie cozy mystery` is a author reference (Agatha Christie); kept out of the backend and of listing recommendations. Judgment `ev_37072f32c6b954b640bf8043`

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

- **placement_upgrade** `cozy mystery`: Ranked #1 (score 0.758) but found only in subtitle (placement 0.80). Consider: title. Evidence: `ev_7042cf5d56b0d974f4db97fa`, `ev_032145039c2e06a55e944a02`, `ev_8b676afc6e54ac3e2de275fa`, `ev_3930a7a6baddb4c5f22b3787` (+2 more)
- **keyword_gap** `amateur sleuth`: Ranked #2 (score 0.756) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_2a0e26132a471052986fdaf9`. Evidence: `ev_bb8680325702dc327ef7604b`, `ev_517ce780c6a55e5b4ae27135`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more)
- **keyword_gap** `small town murder mystery`: Ranked #3 (score 0.687) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_2a0e26132a471052986fdaf9`. Evidence: `ev_94866989109205b68a2acf95`, `ev_f1ac8667c062fc9bd3c6f8da`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more)
- **keyword_gap** `small town mystery books`: Ranked #4 (score 0.674) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Evidence: `ev_ff6e3b8c06891d3ab0929b80`, `ev_f6f5d59a7552836012746768`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more)
- **keyword_gap** `cozy mystery books`: Ranked #5 (score 0.656) but none of its 2 family phrases appears in any weighted field. Consider: title, subtitle, description. Family variants: mystery books cozy. Evidence: `ev_5797890b8641da2711ccc04a`, `ev_ab17863b10dfe2ce5937850f`, `ev_e40e07f72b8611c03eff23bf`, `ev_5001963761dbd34b342a7792` (+3 more)
- **keyword_gap** `small town mystery`: Ranked #6 (score 0.646) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_2a0e26132a471052986fdaf9`. Evidence: `ev_6e477a32477dac3745277165`, `ev_7ca4e84cf849746a7781c6cc`, `ev_869af14ffaddb642bac7273c`, `ev_3930a7a6baddb4c5f22b3787` (+2 more)
- **keyword_gap** `cozy mystery with cats`: Ranked #8 (score 0.535) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_2a0e26132a471052986fdaf9`. Evidence: `ev_d7cb07b78901314f8f48081b`, `ev_55ffac87c8a1334c175608c8`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more)
- **keyword_gap** `cozy mystery series`: Ranked #10 (score 0.506) but the exact phrase appears in no weighted field. Consider: title, subtitle, description. Packed by proposal `prop_2a0e26132a471052986fdaf9`. Evidence: `ev_328805e5168645f27d41f3ac`, `ev_4d5f1b62831d4d8a5988cfd2`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e` (+1 more)

## Proposals

### `prop_2a0e26132a471052986fdaf9`: keywords (evidence)

Packs 7 of 13 ranked keywords, best first, into keywords (3/7 slots). Excluded: 2 entity_flag, 1 in_visible_listing, 3 prohibited_term.

Proposed value: `amateur sleuth small town murder mystery | small town mystery cozy mystery with cats | cozy mystery series small town harbor town`

Validation: **VALID**

Evidence: `ev_bb8680325702dc327ef7604b`, `ev_517ce780c6a55e5b4ae27135`, `ev_3930a7a6baddb4c5f22b3787`, `ev_c77c435fbaf51c5ca439d89e`, `ev_982ab2f536cff485df6b3055`, `ev_94866989109205b68a2acf95`, `ev_f1ac8667c062fc9bd3c6f8da`, `ev_6e477a32477dac3745277165` (+10 more)
