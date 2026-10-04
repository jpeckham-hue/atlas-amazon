# Judgment review queue (v0.8)

Fixture judgments were written before judgments could see the seller's full first-party context. These are the open disagreements between the fixtures and the live models. **Atlas does not change the fixtures.** To record a decision, edit `tests/fixtures/reviews/v08_human_decisions.json` (set `decision` and `rationale`, plus `reviewer` and `decided_at`); decisions become `human` judgments that supersede the fixture as the evaluation reference, and all fixture and model judgments stay in the record.

The *classification* and *proposed* values are Claude's assessment, not a decision.

## book_cozy_mystery: harbor town (relevance)

- Classification: **ambiguous**; proposed: {"score": 0.4}
- Assessment: The description now evidences a harbor setting (ferry dock, harbor festival), so the fixture's 'echoes the title' predates the context; but a setting phrase alone is a weak shopping query. The fast tier's 0.8 over-rates it; the strong tier's 0.45 is close to this proposal.
- First-party context: title *The Quiet Harbor*, subtitle *A Cozy Mystery*; seeds ['cozy mystery', 'small town mystery']; features ['Clean read with no gore or profanity', 'Includes original bakery recipes']; description: "When a body washes up beside the ferry dock, bakery owner Nell Avery must clear her brother's name before the harbor festival."

| Source | Judgment | Confidence | Rationale |
|---|---|---|---|
| fixture | 0.2 | 0.8 | Echoes the title, but readers don't search it. |
| v0.6 live | 0.5 | 0.78 | Title includes 'Harbor'; relevance unclear without confirming story setting. |
| v0.7 fast | 0.8 | 0.85 | Product title The Quiet Harbor and description mention ferry dock; harbor setting is core. |
| v0.7 production | 0.8 | 0.85 | Product title The Quiet Harbor and description mention ferry dock; harbor setting is core. |
| v0.7 strong | 0.45 | 0.55 | Description features a harbor setting, but 'harbor town' alone is generic and not clearly a book search. |

## book_cozy_mystery: small town (relevance)

- Classification: **model_error**; proposed: keep fixture
- Assessment: A setting phrase with no product type; the fixture's 0.3 still holds. The fast tier over-rated it (0.7) once it saw the richer context; the strong tier (0.35) agrees with the fixture.
- First-party context: title *The Quiet Harbor*, subtitle *A Cozy Mystery*; seeds ['cozy mystery', 'small town mystery']; features ['Clean read with no gore or profanity', 'Includes original bakery recipes']; description: "When a body washes up beside the ferry dock, bakery owner Nell Avery must clear her brother's name before the harbor festival."

| Source | Judgment | Confidence | Rationale |
|---|---|---|---|
| fixture | 0.3 | 0.8 | A setting word; on its own not a book search. |
| v0.6 live | 0.4 | 0.75 | 'Small town' matches seed but lacks mystery element; too generic. |
| v0.7 fast | 0.7 | 0.85 | Product set in small harbor town; small town element present and in seller's seeds. |
| v0.7 production | 0.7 | 0.85 | Product set in small harbor town; small town element present and in seller's seeds. |
| v0.7 strong | 0.35 | 0.55 | Small-town setting is implied by seeds, but the phrase alone is generic and names no product type. |

## book_cozy_mystery: mystery books (relevance)

- Classification: **model_error**; proposed: keep fixture
- Assessment: Broad parent category; the fixture's 0.6 holds. The fast tier's 0.8 over-rates it; the strong tier's 0.75 is within tolerance.
- First-party context: title *The Quiet Harbor*, subtitle *A Cozy Mystery*; seeds ['cozy mystery', 'small town mystery']; features ['Clean read with no gore or profanity', 'Includes original bakery recipes']; description: "When a body washes up beside the ferry dock, bakery owner Nell Avery must clear her brother's name before the harbor festival."

| Source | Judgment | Confidence | Rationale |
|---|---|---|---|
| fixture | 0.6 | 0.8 | Broad parent category. |
| v0.6 live | 0.65 | 0.85 | 'Mystery books' matches genre but misses cozy subgenre and small town element. |
| v0.7 fast | 0.8 | 0.85 | Product is a mystery book; matches genre but lacks cozy qualifier. |
| v0.7 production | 0.8 | 0.85 | Product is a mystery book; matches genre but lacks cozy qualifier. |
| v0.7 strong | 0.75 | 0.8 | Right product type (mystery book) but generic; lacks the cozy attribute. |

## book_cozy_mystery: amateur sleuth (relevance)

- Classification: **ambiguous**; proposed: keep fixture
- Assessment: The description now supports the fixture (a bakery owner investigating). The strong tier's 0.6 treats it as a generic trope; the fixture's 0.8 is defensible. Keep the fixture.
- First-party context: title *The Quiet Harbor*, subtitle *A Cozy Mystery*; seeds ['cozy mystery', 'small town mystery']; features ['Clean read with no gore or profanity', 'Includes original bakery recipes']; description: "When a body washes up beside the ferry dock, bakery owner Nell Avery must clear her brother's name before the harbor festival."

| Source | Judgment | Confidence | Rationale |
|---|---|---|---|
| fixture | 0.8 | 0.8 | The protagonist is an amateur sleuth. |
| v0.6 live | 0.6 | 0.75 | Related to mystery genre but doesn't confirm protagonist type from product info. |
| v0.7 fast | 0.7 | 0.8 | Product features amateur sleuth protagonist solving mystery; directly relevant to plot description. |
| v0.7 production | 0.7 | 0.75 | Bakery owner Nell Avery clearing her brother's name is an amateur sleuth premise in a cozy mystery; keyword is a subgenre term, fairly generic but fitting. |
| v0.7 strong | 0.6 | 0.6 | Nell Avery, a bakery owner clearing her brother's name, is an amateur sleuth; fits the plot but is a generic trope. |

## book_cozy_mystery: small town mystery (intent)

- Classification: **model_error**; proposed: keep fixture
- Assessment: Subgenre browsing, as the fixture says. The fast tier still labels it transactional; the strong tier agrees with the fixture.
- First-party context: title *The Quiet Harbor*, subtitle *A Cozy Mystery*; seeds ['cozy mystery', 'small town mystery']; features ['Clean read with no gore or profanity', 'Includes original bakery recipes']; description: "When a body washes up beside the ferry dock, bakery owner Nell Avery must clear her brother's name before the harbor festival."

| Source | Judgment | Confidence | Rationale |
|---|---|---|---|
| fixture | commercial_investigation 0.7 | 0.75 | Subgenre browsing. |
| v0.6 live | transactional 0.95 | 0.96 | Exact seed keyword match; maximum buying intent for this query. |
| v0.7 fast | transactional 0.8 | 0.9 | Specific genre query with strong buying intent for small town mysteries. |
| v0.7 production | transactional 0.8 | 0.9 | Specific genre query with strong buying intent for small town mysteries. |
| v0.7 strong | commercial_investigation 0.55 | 0.65 | Genre/setting query; shopper is browsing small-town mysteries. |

## book_cozy_mystery: cozy mystery books (intent)

- Classification: **ambiguous**; proposed: keep fixture
- Assessment: Genre plus format reads as either ready to buy (fixture, fast tier) or still browsing (strong tier).
- First-party context: title *The Quiet Harbor*, subtitle *A Cozy Mystery*; seeds ['cozy mystery', 'small town mystery']; features ['Clean read with no gore or profanity', 'Includes original bakery recipes']; description: "When a body washes up beside the ferry dock, bakery owner Nell Avery must clear her brother's name before the harbor festival."

| Source | Judgment | Confidence | Rationale |
|---|---|---|---|
| fixture | transactional 0.85 | 0.8 | Looking for books to buy. |
| v0.6 live | transactional 0.88 | 0.92 | Book-specific cozy mystery query; clear buying intent for this format. |
| v0.7 fast | transactional 0.8 | 0.9 | Specific product type query; ready-to-buy intent for cozy mystery books. |
| v0.7 production | transactional 0.8 | 0.9 | Specific product type query; ready-to-buy intent for cozy mystery books. |
| v0.7 strong | commercial_investigation 0.6 | 0.65 | Genre plus 'books' signals shopping for book options, still browsing rather than a specific purchase. |

## physical_water_bottle: bottle water (intent)

- Classification: **model_error**; proposed: keep fixture
- Assessment: A shopper typing 'bottle water' wants to buy bottled water: transactional intent, for a different product. Both tiers conflated 'not this product' with informational intent; relevance (low) is where that belongs.
- First-party context: title *Acme Insulated Water Bottle 32 oz*; seeds ['water bottle', 'insulated water bottle']; features ['Leak proof lid with carry loop', 'Double wall vacuum insulation keeps drinks cold for 24 hours', 'Fits most cup holders']; description: "A sturdy stainless steel bottle for everyday hydration."

| Source | Judgment | Confidence | Rationale |
|---|---|---|---|
| fixture | transactional 0.8 | 0.8 | Buying bottled water. |
| v0.6 live | transactional 0.85 | 0.9 | 'Bottle water' suggests shopping for water in containers, with purchase intent but ambiguous product type. |
| v0.7 fast | informational 0.1 | 0.95 | 'Bottle water' refers to drinking water in bottles, not a water bottle container for hydration. |
| v0.7 production | informational 0.1 | 0.95 | 'Bottle water' refers to drinking water in bottles, not a water bottle container for hydration. |
| v0.7 strong | informational 0.15 | 0.5 | 'Bottle water' reads as the drink, so shopper likely wants bottled water or information, not a container; weak purchase intent. |

## physical_water_bottle: stainless steel (relevance)

- Classification: **stale_reference**; proposed: {"score": 0.65}
- Assessment: The listing description states the bottle is stainless steel, which the fixture's 'material match' predates. The keyword is still generic without a product type, so mid-high rather than high; the strong tier's 0.65 matches.
- First-party context: title *Acme Insulated Water Bottle 32 oz*; seeds ['water bottle', 'insulated water bottle']; features ['Leak proof lid with carry loop', 'Double wall vacuum insulation keeps drinks cold for 24 hours', 'Fits most cup holders']; description: "A sturdy stainless steel bottle for everyday hydration."

| Source | Judgment | Confidence | Rationale |
|---|---|---|---|
| fixture | 0.55 | 0.7 | Material match, but very generic. |
| v0.6 live | 0.5 | 0.8 | Common water bottle material, but not confirmed in title or seeds; treated as unknown. |
| v0.7 fast | 0.85 | 0.9 | Stainless steel is stated in product description as the bottle material; clearly relevant attribute. |
| v0.7 production | 0.85 | 0.9 | Stainless steel is stated in product description as the bottle material; clearly relevant attribute. |
| v0.7 strong | 0.65 | 0.7 | Description states stainless steel bottle, so material matches, but keyword is generic without a product type. |
