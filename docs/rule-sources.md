# Rule sources and verification status

Last verification pass: **2026-10-03**. Every value below was read from the
linked page on that date. The recipes in `src/atlas_amazon/recipes/data/`
are the source of truth, and `tests/test_recipes.py` pins every verified
value to its URL, so this page and the code can't drift apart silently.

| Status | Meaning |
|---|---|
| **verified** | Confirmed on `as_of` against an official Amazon policy page (Seller Central Help, KDP Help, Amazon Ads or SP-API docs). The loader rejects a `verified` source without such a URL, and forum threads don't count. |
| **unverified** | Attributed, but not confirmable from official documentation. The source's `note` says why. Still enforced, because a conservative default beats none, but findings show the status. |
| **heuristic** | An atlas convention, not an Amazon rule. Always `warning` severity. |

Third-party pages (blogs, tool vendors) and forum threads are recorded in a
source's `see_also` list. They never back a `verified` status.

## Seller Central: `physical-product` (US)

Scope: the title requirements apply to "all product types, except media
product types" in all stores except Saudi Arabia, Egypt, Türkiye and the
UAE. Media product types include `ABIS_BOOK` and `ABIS_EBOOKS`
([GMF8CVX6S6CF8MM2](https://sellercentral.amazon.com/help/hub/reference/external/GMF8CVX6S6CF8MM2)).

### Verified

| Rule / limit | Value | Severity | Source |
|---|---|---|---|
| Title length | ≤ 75 chars incl. spaces (effective 2026-07-27, replacing 200) | error | [Product title requirements](https://sellercentral.amazon.com/help/hub/reference/external/GYTR6SYGFA5E3EQC) |
| Item highlights | ≤ 125 chars | error | same |
| Title word repetition | same word ≤ 2×; prepositions, articles and conjunctions exempt; brand names not exempt | error | same |
| Title special characters | `! $ ? _ { } ^ ¬ ¦` | error | same |
| Title promotional phrases | "free shipping", "100% quality guaranteed" (verbatim examples) | error | same |
| Title restricted phrases | "FSA/HSA eligible" | error | same |
| Title subjective commentary | "hot item", "best seller" (a best practice, not a requirement) | warning | same |
| Bullet prohibited claims | eco-friendly, anti-microbial, made from bamboo, … (verbatim list) | error | [Product bullet point requirements](https://sellercentral.amazon.com/help/hub/reference/external/GX5L8BF8GLMML6CX) |
| Bullet guarantee information | "full refund", … | error | same |
| Bullet placeholder text | "not applicable", "n/a", "TBD", … | error | same |
| Bullet special characters | `™ ® € … † ‡ ¢ £ ¥ © ± ~` | error | same |
| Search terms length | **< 250 bytes** (max 249) | error | [Search optimization](https://sellercentral.amazon.com/help/hub/reference/external/GNYWHX2TP7C8GXHK) |
| Search terms stopwords | articles, prepositions, short words ("a", "and", "or", "the", "with") | packing | same |
| Search terms repetition | no repeats; singular *or* plural | warning | same |
| Search terms prohibited | "new", "on sale now", "best", "cheapest" (verbatim examples) | error | same |

### Unverified (kept, with reasons)

| Limit | Value kept | Why it's unverified |
|---|---|---|
| Bullet count | max 5 | The official bullet page gives no maximum, only "include at least three". |
| Bullet length | 500 chars | The official page says limits "vary by product type". |
| Description length | 2000 chars | No official help page states it. Only seller forum threads (in `see_also`). |
| Search terms: do spaces count? | yes (conservative) | The official page says "less than 250 bytes" without defining whether spaces count. |

All three numeric limits are defined per product type in the **SP-API
Product Type Definitions API** (`bullet_point`, `product_description`,
`generic_keyword`). Reading those schemas is the way to verify them, and
needs a live provider, so it's deferred.

### Heuristic

| Rule | Why it's a heuristic |
|---|---|
| `title_promotional_extended` ("bestseller", "on sale", "limited time", …) | atlas-curated, beyond Amazon's examples |
| `backend_visible_overlap` (backend words already visible in title/bullets) | Official guidance only says not to repeat words *within* search terms |

## KDP: `book`

The Seller Central product title requirements **do not apply** (books are
exempt media types), so the book recipe inherits none of them.

### Verified

| Rule / limit | Value | Severity | Source |
|---|---|---|---|
| Title + subtitle | **fewer than 200 chars combined** (max 199) | error | [Metadata Guidelines for Books](https://kdp.amazon.com/en_US/help/topic/G201097560) |
| Title/subtitle sales-rank and promotion references | "bestselling", "free" (verbatim examples) | warning (a word like "free" can be a genuine title) | same |
| Title/subtitle HTML tags | `<` `>` as a proxy | error | same |
| Keyword sales-rank and promotion references | "bestselling", "free" | error | same |
| Keyword HTML tags | `<` `>` | error | same |
| Description length | ≤ 4000 chars, HTML tags included | error | [Write a Book Description](https://kdp.amazon.com/en_US/help/topic/G201189630) |
| Keyword count | up to 7 | error | [Keywords](https://kdp.amazon.com/en_US/help/topic/G201298500) |
| Keywords to avoid | "new", "on sale", "available now", "Kindle Unlimited", "KDP Select", "book" | warning (framed as "avoid") | same |
| Keyword quotation marks | `"` `“` `”` | warning | same |

### Unverified

| Limit | Value kept | Why it's unverified |
|---|---|---|
| Keyword box length | 50 chars | The KDP page only says "keep an eye on the character limit in the text field". The number 50 comes from the KDP form and third-party guides (in `see_also`). |

### Documented but not enforced deterministically

These need entity or semantic judgment (LLM plus human review):
other authors' names and books in titles or keywords, unauthorized
trademarks, keywords unrelated to content, print titles matching the cover,
titles consisting only of placeholders ("unknown", "n/a", …) or only
punctuation, and description content rules (reviews, contact details,
spoilers, time-sensitive information).

## Changes in the 2026-10-03 pass

| Was | Now | Why |
|---|---|---|
| Product title ≤ 200 chars in `amazon-base` | ≤ 75 chars in `physical-product` | Official limit changed 2026-07-27, and media is exempt |
| Title rules inherited by `book` (then disabled) | Not inherited at all | Seller Central rules exempt `ABIS_BOOK`/`ABIS_EBOOKS` |
| Search terms ≤ 250 bytes | ≤ 249 bytes | "less than 250 bytes" |
| KDP title + subtitle ≤ 200 | ≤ 199 | "fewer than 200 characters" |
| KDP subtitle ≤ 200 on its own | no standalone limit | not documented |
| One promotional-terms list | split into verified examples (error), verified best practice (warning) and atlas extensions (heuristic warning) | separates Amazon rules from atlas judgment |
| One backend redundancy rule | `backend_repetition` (verified) and `backend_visible_overlap` (heuristic) | only the former is official guidance |
| — | new: `item_highlights` field, bullet prohibited content, restricted phrases, backend prohibited terms, KDP HTML, quotes and avoid-terms rules | documented on the official pages |
| KDP 7 × 50 under one source | count verified, 50 chars unverified (per-limit sources) | 50 isn't stated in KDP Help |
