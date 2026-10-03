# Architecture

## Goals

Given product or book metadata (plus an optional ASIN and competitor ASINs),
atlas-amazon should:

1. **Research**: competitors, keywords, review themes, listing structure.
2. **Store evidence**: every observed fact keeps its provider, marketplace,
   retrieval timestamp, source URL and raw payload.
3. **Rank keywords**: by relevance, demand, competition, intent and
   competitor coverage, using a decomposable formula.
4. **Audit** the current listing against a recipe: limits, compliance,
   coverage.
5. **Plan and generate** a proposed title, bullets, description and backend
   keywords, where each proposal links back to evidence.
6. **Validate deterministically** every proposal, whether it came from a
   human or an LLM.
7. **Require human approval** before any publish or update action.

## Layers

```
            ┌───────────────────────────────────────────────────────────────┐
 input  ──▶ │ ProductInput (metadata, ASIN?, competitor ASINs, recipe_id)   │
            └───────────────┬───────────────────────────────────────────────┘
                            ▼
 providers  Catalog · KeywordData · Suggestion · Review Protocols (v0.2: fixture
            fakes only; live SP-API / keyword vendor / autocomplete later)
                            ▼
 evidence   Evidence(id, kind, provider, marketplace, retrieved_at, payload,
            source_url, subject, run_id); append-only, checksummed JSONL store
                            ▼
 domain     recipes ─▶ keyword scoring ─▶ coverage ─▶ audit ─▶ proposals
 (pure)     all deterministic and side-effect free; a proposal is valid only
            after it passes the audit and its evidence resolves
                            ▼
 semantic   LLM steps (relevance judgments, review themes, drafting copy)
 (planned)  every output goes back through deterministic validation
                            ▼
 review     human approval gate: diff of current vs proposed + evidence trail
                            ▼
 publish    SP-API listing patch / KDP export. Never automatic.
 (planned)
```

The domain layer never imports providers, LLM clients or I/O. Providers and
LLMs are injected at the edges, so the core stays testable offline and
reproducible.

## File tree

`✓` = exists (v0.4b), `·` = planned.

```
atlas-amazon/
├── .gitattributes                 ✓ LF normalization for Windows/Linux
├── pyproject.toml                 ✓ hatchling; no runtime deps; pytest + ruff dev
├── README.md                      ✓
├── docs/
│   ├── architecture.md            ✓ this file
│   ├── examples/                  ✓ golden example research reports
│   └── rule-sources.md            ✓ verified / unverified / heuristic rule inventory
├── src/atlas_amazon/
│   ├── models.py                  ✓ ProductInput, Listing, Evidence, EvidenceKind, SourceRef,
│   │                                Finding, AuditReport
│   ├── jsonvalue.py               ✓ JSON-only deep freeze/thaw, canonical JSON
│   ├── recipes/
│   │   ├── schema.py              ✓ Recipe, FieldSpec, RuleSpec, BackendSpec, KNOWN_CHECKS
│   │   ├── loader.py              ✓ TOML load, `extends` merge, strict validation
│   │   └── data/
│   │       ├── amazon-base.toml   ✓
│   │       ├── book.toml          ✓
│   │       └── physical-product.toml ✓
│   ├── keywords/
│   │   ├── normalize.py           ✓ normalize_text, tokenize, fold_plural, keyword_key, dedupe
│   │   ├── coverage.py            ✓ exact/token/placement coverage
│   │   ├── scoring.py             ✓ decomposable keyword score, ranking, signal transforms
│   │   ├── candidates.py          ✓ keyword candidates from seeds/suggestions/competitors
│   │   ├── families.py            ✓ keyword families: explained equivalence links
│   │   └── signals.py             ✓ family signals; judgment or heuristic sources
│   ├── backend/
│   │   └── packing.py             ✓ byte-budget and slot packing with exclusion reasons
│   ├── audit/
│   │   └── listing.py             ✓ field limits, required fields, rule checks registry
│   ├── evidence/
│   │   ├── identity.py            ✓ content-addressed evidence IDs, make_evidence
│   │   ├── serialize.py           ✓ checksummed JSON records
│   │   ├── store.py               ✓ EvidenceStore Protocol, errors, InMemoryEvidenceStore
│   │   └── jsonl.py               ✓ append-only JsonlEvidenceStore
│   ├── providers/
│   │   ├── base.py                ✓ Catalog/KeywordData/Suggestion/Review Protocols
│   │   ├── fixtures.py            ✓ fixture-backed fakes
│   │   ├── sp_api.py              ·
│   │   ├── autocomplete.py        ·
│   │   └── nexscope.py            ·
│   ├── planner/
│   │   ├── proposal.py            ✓ Proposal, ProposalBasis, validate_proposal
│   │   └── recommend.py           ✓ backend plan, keyword gaps, placement upgrades
│   ├── research/
│   │   ├── run.py                 ✓ ResearchRun orchestration, ResearchResult
│   │   ├── tasks.py               ✓ research priority -> task registry
│   │   └── scenarios.py           ✓ offline scenario loader
│   ├── judgments/
│   │   └── contract.py            ✓ JudgmentRequest, judgment Evidence, parse_judgment
│   ├── semantic/
│   │   ├── prompts/*.toml         ✓ versioned prompt templates + lock.json fingerprints
│   │   ├── llm.py                 ✓ LLMJudgmentProvider, LLMReviewThemeProvider
│   │   ├── transport.py           ✓ Anthropic (live) / Recording / Replay / Scripted
│   │   ├── cache.py               ✓ persistent semantic cache
│   │   ├── usage.py, pricing.py   ✓ usage ledger, hard limits, cost estimates
│   │   ├── human.py               ✓ human judgments + override resolution
│   │   ├── evaluation.py          ✓ per-type agreement vs reference judgments
│   │   ├── records.py             ✓ checksummed JSONL + secret guard
│   │   └── synthetic.py           ✓ scripted responses for offline demo recordings
│   ├── reviews/
│   │   └── themes.py              ✓ review-theme Evidence, summaries, opportunities
│   ├── report/
│   │   └── render.py              ✓ report dict / JSON / Markdown (formatting only)
│   ├── llm/                       · prompt contracts; outputs re-validated
│   └── review/                    · approval records; publish is gated on approval
└── tests/                         ✓ one module per domain module; fixtures/ for fakes
```

## Domain model

| Model | Purpose |
|---|---|
| `ProductInput` | User-supplied metadata, recipe id, marketplace, optional ASIN and competitor ASINs (validated format, no self-competition). |
| `Listing` | Recipe-agnostic `field -> str \| tuple[str]` map. The recipe decides what the fields mean. |
| `Evidence` | One observed fact: provider, marketplace, timezone-aware `retrieved_at`, `source_url`, `subject`, `run_id`, and a JSON-only, deeply frozen payload. See [Evidence store](#evidence-store-v02). |
| `SourceRef` | Provenance for a *rule*: title, `as_of` date, status (`verified` / `unverified` / `heuristic`), URL, marketplace, scope, note, and `see_also` (non-authoritative references kept apart from `url`). |
| `Finding` | An audit result with rule id, severity, observed value, limit and the rule's `SourceRef`. |
| `AuditReport` | Findings plus `passed` (no errors). Warnings and info don't fail an audit. |

Two different kinds of provenance:

* **Evidence** is about the *market*: "competitor X's title on 2026-10-01 was …".
* **SourceRef** is about the *rules*: "the 75-character product title limit
  comes from Seller Central Help page GYTR6SYGFA5E3EQC, verified 2026-10-03".

## Recipes

A recipe is a TOML file with these sections:

| Section | Meaning |
|---|---|
| `id`, `version`, `description`, `extends` | Identity and a single parent. These keys are never inherited. |
| `[sources.<id>]` | Dated provenance entries referenced by fields, rules and the backend: `title`, `as_of`, `status`, `url`, `marketplace`, `scope`, `note`, `see_also`. A `verified` source needs an https URL on an official Amazon policy host (not a forum). An `unverified` source needs a `note`. |
| `[fields.<name>]` | `kind` (`text`/`list`), `required`, and limits: `max_chars`, `max_bytes`, `min_count`, `max_count`, `item_max_chars`, `item_max_bytes`. **Every limit must resolve to a source**: the field's `source`, or a per-limit override in `limit_sources = { item_max_chars = "..." }` when one field's limits are documented in different places or verified to different degrees. |
| `[rules.<id>]` | `check` (one of `KNOWN_CHECKS`), `severity`, `source` (mandatory), `fields`, `enabled`, plus the check's params. |
| `[backend]` | Which field holds hidden keywords and how it's budgeted: `mode = "bytes"` (text field with `max_bytes`) or `mode = "slots"` (list field with `max_count` × `item_max_chars`). |
| `[scoring.keyword]` | Weights for the five keyword signals. Must sum to 1. |
| `[scoring.coverage]` | Relative field weights for placement scoring. |
| `[research] priorities` | Ordered research tasks for the (planned) research orchestrator. |

**Merge semantics:** the chain is merged root first. Tables merge key by key
and every other value (lists included) is replaced by the child. That lets a
child override part of a rule, e.g. change a rule's severity while keeping
its inherited terms, or disable it with `enabled = false`.

**Strictness:** unknown keys, unknown checks, unsourced limits, rules without
sources, dangling field references, invalid backend shapes and keyword
weights that don't sum to 1 all raise `RecipeError` at load time.

### Built-in recipes

Full rule-by-rule status, with links, is in [rule-sources.md](rule-sources.md).

* **amazon-base**: shared field vocabulary (`title` required, `description`)
  and default weights. It deliberately has **no limits and no rules**:
  Seller Central and KDP document different rules, and the Seller Central
  title requirements exempt media product types, books included.
* **physical-product** (Seller Central, US): title ≤ 75, item highlights
  ≤ 125, search terms < 250 bytes (all verified), title, bullet and
  search-term content rules (verified), bullets 5 × 500 and description
  2000 (unverified: these vary by product type), and two heuristic warning
  rules.
* **book** (KDP Help): title + subtitle < 200 combined, description ≤ 4000,
  7 keyword boxes, KDP title and keyword content rules (all verified), and a
  50-character keyword box (unverified). Entity checks (other authors,
  trademarks) and "title matches cover" are left to LLM/human review.

`tests/test_recipes.py` pins every verified limit and rule to its exact
URL. It also requires every limit to be either pinned as verified or
explicitly listed as knowingly unverified.

## Deterministic utilities

### Normalization

`normalize_text`: NFKC → casefold → remove apostrophes (`women's` → `womens`)
→ every other non-word character becomes a space → collapse whitespace.

`fold_plural` is a **matching-only** key and is never displayed. Its rules,
in order: tokens of 3 characters or fewer, non-alphabetic tokens and listed
exceptions are kept as they are; `-ies` → drop `s`; consonant + `y` → `ie`;
`-sses/-shes/-ches/-xes/-zes` → drop `es`; `-ss/-us/-is` are kept; otherwise
a trailing `s` is dropped. So `baby`/`babies` → `babie` and
`cookie`/`cookies` → `cookie`. It is a deliberately small, predictable
heuristic, not a stemmer.

### Coverage

For keyword *k* and weighted field *f* with weight *w_f*:

* `exact(k,f) = 1` if *k*'s folded tokens appear contiguously in one
  segment of *f*. Segments are a text field, or one list item, so phrases
  never span bullets.
* `token_fraction(k) = |unique(k) ∩ tokens(all weighted fields)| / |unique(k)|`
* `placement(k) = max_{f : exact(k,f)} w_f / max_g w_g`, else 0

Report aggregates: `exact_rate`, `token_rate` and `placement_score` are
means over the deduplicated keywords. Every per-keyword value is kept.

### Backend packing

* **bytes mode**: tokenize candidates in priority order. Drop stopwords,
  duplicates (by folded key) and words already visible in the listing. Add
  each word greedily if the UTF-8 length of the space-joined result stays
  within budget. If a word doesn't fit, it's skipped and packing keeps
  trying later, shorter words.
* **slots mode**: phrases stay intact. Drop duplicates (by key) and phrases
  whose every word is already visible. Place first-fit across N slots of M
  characters.
* Every candidate that isn't packed is returned with an `ExclusionReason`
  (`empty`, `stopword`, `duplicate`, `in_visible_listing`, `too_long`,
  `over_budget`).

### Audit

`audit_listing(listing, recipe)` runs these steps:

1. Unknown fields → `info`. They aren't audited, and they're never dropped
   silently.
2. Required fields that are missing or blank → `error`.
3. Field limits → `error` (chars, bytes, count, per-item chars and bytes,
   kind mismatch).
4. Each enabled rule → its check from the `CHECKS` registry: `word_repetition`,
   `prohibited_terms` (plural-folded, whole-phrase, checked per segment),
   `disallowed_characters`, `combined_length`, `backend_repetition` (repeats
   within the backend field) and `backend_visible_overlap` (backend words
   already visible). Field-limit findings cite the per-limit source.

A test asserts that `CHECKS` and `KNOWN_CHECKS` stay in sync.

## Scoring (v0.2)

`keywords/scoring.py`. No score in atlas-amazon is a black box:

```
score(k) = Σ_s  w_s · x_s(k)        s ∈ KEYWORD_SIGNALS
x_s = raw_s                          for relevance, demand, intent, competitor_coverage
x_competition = 1 − raw_competition  (supplied as "how competitive", scored inverted)
```

* **Inputs.** A `KeywordSignals` holds five `SignalValue(value ∈ [0, 1],
  evidence_ids)`. Values outside [0, 1], NaN or infinity are rejected,
  and there is no default for a missing signal: the caller must choose one
  explicitly.
* **Weights.** The recipe's `[scoring.keyword]`, re-validated at scoring
  time: exactly the five signals, finite, non-negative, summing to 1. That
  means `score ∈ [0, 1]`.
* **Output.** `KeywordScore` holds the score plus one `SignalContribution`
  per signal: raw value, normalized value, `inverted` flag, weight,
  contribution (`weight × normalized`) and evidence IDs. `score` is exactly
  `math.fsum` of the contributions. A signal with no evidence IDs is still
  scored, but it is listed in `heuristic_signals`.
* **Ranking.** `rank_keywords` sorts by descending score, breaking ties on
  the plural-folded keyword key. It rejects candidates that fold to the same
  key (e.g. "water bottle" and "Water Bottles").
* **Documented transforms** from raw evidence to signals:
  * `log_scaled_signal(v, ceiling) = log1p(v) / log1p(ceiling)`, clamped.
    Used for search volume, with the ceiling set to the candidate-set
    maximum.
  * `linear_signal(v, low, high)`, clamped.
  * `competitor_coverage_signal(k, [(evidence_id, Listing)])` = the share
    of competitor listings with *k*'s exact phrase in any one segment. It
    is backed by **all** examined competitors' evidence, because the
    denominator depends on every one of them.
* LLM-derived signals (relevance, intent; v0.4+) will be recorded as
  Evidence (model, prompt version, timestamp) and cited like any other
  signal.

## Evidence store (v0.2)

`evidence/`. Evidence is the record of *what was observed*. It is append-only
and tamper-evident.

* **Model.** `Evidence(id, kind, provider, marketplace, retrieved_at,
  payload, source_url, subject, run_id)`. `retrieved_at` must be
  timezone-aware. `payload` must be JSON-compatible (no NaN or infinity,
  string keys only) and is deeply frozen (read-only mappings, tuples).
  `subject` is what the fact is about (an ASIN, keyword or seed), and
  `run_id` groups one research run.
* **Identity.** `make_evidence` derives a content-addressed ID:
  `ev_` + SHA-256 (truncated to 96 bits) of the canonical JSON of
  provider, kind, marketplace, subject, run and payload. The retrieval
  time is deliberately left out, so re-observing the same fact within one
  run collides with the existing record instead of double-counting it.
* **Protocol.** `EvidenceStore` defines `append`, `append_many`
  (all-or-nothing), `get`, `in`, `len`, `iter` and
  `query(run_id, subject, kind, provider, marketplace)`. Filters are ANDed
  and results keep insertion order. There is no update or delete.
* **`InMemoryEvidenceStore`** has the same contract, for tests.
* **`JsonlEvidenceStore`** writes one canonical-JSON line per record:
  `{"evidence": {...}, "sha256": "...", "v": 1}`.
  * The file is opened only in append mode. A batch is validated in full
    (types, duplicates against the store and within the batch) before any
    write, then written in one call and fsynced.
  * On open, every line is verified. Invalid JSON, a checksum mismatch, a
    wrong version or key set, a truncated last line, a blank line or a
    duplicate ID raises `CorruptEvidenceError(path, line, reason)`. Nothing
    is skipped.
  * `verify()` re-reads the file and confirms it matches the store's
    records exactly, which catches appends, replacements and deletions by
    other processes.
  * It is single-writer: there is no cross-process locking (documented
    limitation).

## Providers (v0.2: protocols and fakes only)

`providers/`. Each provider implements one narrow, `runtime_checkable`
Protocol and returns `list[Evidence]`, never raw dicts:

| Protocol | Method | Evidence kind | Future live adapter |
|---|---|---|---|
| `CatalogProvider` | `get_items(asins, *, marketplace, run_id)` | `catalog_item` | SP-API Catalog/Listings Items |
| `KeywordDataProvider` | `keyword_metrics(keywords, *, marketplace, run_id)` | `keyword_metric` | Nexscope or similar |
| `SuggestionProvider` | `suggestions(seed, *, marketplace, run_id)` | `autocomplete_suggestion` | Amazon autocomplete |
| `ReviewProvider` | `reviews(asin, *, marketplace, run_id, limit)` | `review_sample` (one per review) | review data vendors |

Conventions: `marketplace` is always required, and `run_id` is stamped on
every record. A provider with no data for an item returns nothing for it,
never an invented default.

**Fixture fakes** (`providers/fixtures.py`) read one JSON document with
optional `catalog`, `keyword_metrics`, `suggestions` and `reviews` sections,
keyed by marketplace. They are deterministic: a fixed `retrieved_at` from
the fixture, content-addressed IDs, and `fixture://<file>#<section>/<mkt>/<key>`
source URLs. Keyword and seed lookups use normalized text. Fixture shape
errors raise `FixtureError`.

A future `ListingWriter` (SP-API Listings patch) will only be callable
with an approval record.

## Proposals (v0.2)

`planner/proposal.py`. A `Proposal` is one suggested value for one field:
`id`, `recipe_id`, `recipe_version`, `target_field`, `value`, `rationale`,
`evidence_ids`, `basis` and `created_at` (timezone-aware).

* **Evidence or explicitly heuristic.** With no evidence IDs, the basis
  must be `heuristic` (`Proposal.create(..., heuristic=True)`). A heuristic
  proposal may not cite evidence. Both rules are enforced in the
  constructor, so `dataclasses.replace` can't get around them.
* **Deterministic ID.** `prop_` + a hash of the content and `created_at`.
* **No validity flag on the proposal.** Validity exists only as the result
  of `validate_proposal(proposal, recipe=, base=, evidence=)`, which
  returns a `ProposalValidation`:
  1. structural `problems`: wrong recipe or recipe version, unknown field,
     or text/list shape mismatch (the audit is skipped);
  2. `missing_evidence`: cited IDs not in the evidence store;
  3. the existing `audit_listing` run on `proposal.apply_to(base)`, with
     `blocking_findings` = error findings on the target field, or from
     cross-field rules that include it (e.g. KDP title+subtitle length).

  `valid` is true only when all three are empty. Errors elsewhere in the
  base listing appear in the full `audit` but don't block the proposal.
  Warnings never block.

## Research workflow (v0.3)

The first end-to-end question atlas can answer: *"Here is a book or
listing. Which keywords matter, what am I missing, why, and what should
change?"* It is fully offline and deterministic.

```
ResearchRun(product, listing, recipe_id, run_id, providers, store, started_at)
  1 collect    for each recipe research.priority -> task (research/tasks.py)
               provider -> Evidence -> store   (always stored before use)
  2 derive     store.query(run_id) -> build_candidates -> derive_signals
               -> rank_keywords (v0.2 scoring)
  3 assess     audit_listing(current listing, recipe)
  4 recommend  plan_backend -> Proposal ; keyword_recommendations
               validate_proposal(each proposal)
  -> ResearchResult -> report_dict / report_json / render_markdown
```

**Separation of concerns.**

| Layer | Modules | May | May not |
|---|---|---|---|
| Orchestration | `research/run.py`, `research/tasks.py` | choose providers and inputs per priority, store evidence, call domain functions, account for missing data | score, rank, judge or invent values |
| Providers | `providers/*` | return Evidence | score or rank |
| Domain | `keywords/candidates.py`, `keywords/signals.py`, `keywords/scoring.py`, `planner/recommend.py`, `audit/` | compute everything | do I/O |
| Report | `report/render.py` | copy and format result fields | compute, threshold or decide |

**Priorities to tasks.** Several priorities can share one task, which runs
once; later priorities record `already_done`. Priorities with no offline
task are recorded as `unsupported`. A task without a provider is
`no_provider`, and one without inputs is `no_input`.

| Priorities | Task | Provider calls |
|---|---|---|
| competitor_titles, competitor_bullets, comparable_titles, category_attributes | `competitor_catalog` | `get_items(competitor ASINs)` |
| search_term_demand | `search_demand` | `suggestions(seed)` per seed, then `keyword_metrics(candidates built from evidence stored so far)` |
| review_themes, reader_review_themes | `competitor_reviews` | `reviews(asin)` for the product and its competitors. Stored and summarized only: theme analysis needs semantic judgment (v0.4) |
| browse_categories, series_and_format_signals | (none) | recorded `unsupported` |

Order matters, and comes from the recipe. If `search_term_demand` runs
before competitor catalog data exists, competitor phrases get no metrics
and show up as unscored with that reason.

**Seeds.** Seeds come from `product.attributes["seed_keywords"]`, falling
back to the product title. The metadata records which source was used.

**Keyword candidates** (`keywords/candidates.py`), merged by plural-folded
key, with sources and evidence IDs unioned:
seeds, suggestion strings, the current listing's keyword-box phrases (slots
backends), and 2–3-word competitor phrases shared by at least
`min_competitor_support` (default 2) competitors. Shared phrases may not
start or end with a stopword or be digits only.

**Signals** (`keywords/signals.py`):

| Signal | Source | Formula |
|---|---|---|
| demand | `keyword_metric` | `log1p(volume) / log1p(max volume among candidate metrics)` |
| competition | `keyword_metric` | metric `competition` ∈ [0, 1], scored as `1 − value` |
| competitor_coverage | `catalog_item` | share of competitors with the exact phrase in one segment |
| relevance | **judgment** if available (v0.4a), else **heuristic**: share of non-stopword keyword terms found in the product title or seeds |
| intent | **judgment** if available (v0.4a), else **heuristic**: `min(1, words / 4)`, a specificity proxy |

Heuristic signals carry no evidence IDs, so every score lists them in
`heuristic_signals` and every report marks them. **No defaults:** a
candidate missing any evidence-derived signal (no metric, an invalid
volume or competition, no competitors) is reported as *unscored* with a
per-signal reason, and is never ranked on an invented value. Each signal
also carries a derivation note, e.g. `log1p(9000) / log1p(120000) from ev_…`.

**Recommendations** (`planner/recommend.py`). No copywriting.

* `plan_backend` packs ranked keywords, best first, into the backend field.
  The byte budget for Seller Central search terms, or 7 phrase slots for
  KDP. Before packing:
  * keywords hitting any enabled `prohibited_terms` rule on the backend
    field are removed, citing the rule;
  * words in `[backend] visible_fields` are skipped;
  * the listing's **current backend content is retained at the lowest
    priority**. The rationale names what was retained and what was dropped,
    so nothing disappears silently.

  The proposal cites the evidence of every contributing keyword and is
  omitted when it would equal the current value.
* `keyword_recommendations` covers the top-N ranked keywords:
  * `keyword_gap`: the exact phrase is in no weighted field;
  * `placement_upgrade`: the phrase is only in a lower-weight field.

  Suggested fields are ordered by coverage weight. Fields where a recipe
  rule forbids the keyword are listed as `blocked_fields` with the rule ID.
  A gap the backend proposal already packs links to that proposal.

**Reproducibility.** There is no wall clock (`started_at` is an input) and
no randomness. Evidence IDs are content-addressed, and every collection is
built in insertion or sorted order. The same fixtures, recipe version,
inputs and `started_at` give an equal `ResearchResult` and byte-identical
reports. Re-running a `run_id` on the same store reuses its evidence
(`reused_records`) instead of duplicating it.
`metadata.evidence_fingerprint` hashes the sorted evidence IDs a run
used.

**Report** (`report/`): `report_dict` (JSON-ready), `report_json` and
`render_markdown`. Sections: run metadata, research tasks, evidence summary
(including explicit gaps: competitors without catalog, seeds without
suggestions, candidates without metrics, ASINs without reviews), current
audit with rule provenance, ranked keywords, per-keyword signal breakdown
with evidence and derivation, unscored keywords, recommendations,
proposals with validation. Examples:
[book](examples/book_cozy_mystery.md),
[physical product](examples/physical_water_bottle.md). A golden test keeps
them current.

**Scenarios** (`research/scenarios.py`, `tests/fixtures/scenarios/`): one
JSON per scenario (inputs, configured provider roles, fixture data):
`book_cozy_mystery`, `physical_water_bottle`, `partial_missing_data` (no
suggestion or review provider, a competitor missing from the catalog,
incomplete metrics) and `well_covered_listing`.

## Semantic layer (v0.4a, offline)

v0.4a prepares the semantic layer with no external dependencies. Everything
semantic is either a deterministic, explainable rule or a recorded
**judgment** (Evidence) from a `JudgmentProvider`. Today that provider is
fixture-backed; in v0.4b it can be an LLM.

### Keyword families (`keywords/families.py`)

Ranking operates on **families** of phrases that are the same search
concept. Reports still list every phrase.

| Link | When | Example |
|---|---|---|
| (candidate merge) | same plural-folded key; happens earlier in `build_candidates` | "water bottle" / "Water Bottles" |
| `stopword_variant` | same content words, same order; one phrase only *adds* connecting words | "water bottle for kids" ~ "water bottle kids" |
| `attribute_rotation` | an attribute-like block (1–2 words) moves between the front and back of an intact core of ≥ 2 words | "insulated water bottle" ~ "water bottle insulated"; "32 oz water bottle" ~ "water bottle 32 oz" |
| `judgment` | a *candidate pair* (same words, other order) confirmed by an `equivalence` judgment with confidence ≥ `min_equivalence_confidence` (0.7) | "kids water bottle" ~ "water bottles for kids" |

Attribute-like means one of:
* a number, a unit, or a listed attribute word;
* a 5+ letter word ending in -ed, -less, -proof, -free, -able, -ible, -ful or -ous;
* a two-word block that ends in proof/free/resistant/safe or starts with an attribute.

**Never grouped automatically:**
* noun swaps ("water bottle" / "bottle water");
* head-noun moves ("dog food bowl" / "bowl dog food");
* substituted connecting words ("mug for tea" / "mug with tea");
* different specificity ("cozy mystery" / "cozy mystery books").

Candidate pairs without a judgment are reported as *unconfirmed*; judged
"not equivalent" (or low-confidence) pairs as *rejected*, citing the
judgment. A judgment can only confirm a deterministic candidate pair. It
can't join unrelated phrases.

* **Family ID**: `fam_` + hash of the sorted member keys, independent of
  the label.
* **Canonical label**: the member with the highest search volume;
  otherwise fewest words, then shortest text, then alphabetical. The
  reason is recorded.
* **Aggregation without double counting** (`derive_signals`):
  * demand = log-scaled **sum** of distinct members' volumes (each metric
    evidence once);
  * competition = volume-weighted mean;
  * competitor coverage = the share of competitors containing **any**
    member (each competitor once).
* **Coverage**: a family is covered if any member appears, and its
  placement is the best member's placement.
* **Backend packing**: packs the canonical only. Other members share its
  words and are listed as `redundant_members`.

`ResearchConfig(keyword_families=False)` disables grouping, which is used
to compare outputs.

### Judgment contract (`judgments/contract.py`)

`JudgmentRequest(type, input)` has four types: `relevance`, `intent`,
`entity` and `equivalence`. The input is frozen JSON. Keyword requests
carry `{keyword, context: {product_title, seeds}}`; equivalence carries
`{phrases: [a, b]}`, sorted. `input_hash = sha256(canonical {"type",
"input"})`.

Judgment Evidence (`kind = "judgment"`) payload:
`judgment_type, input, input_hash, result, confidence, model,
prompt_version, rationale`. The envelope supplies provider, marketplace,
timestamp (`retrieved_at`), run_id and subject.

| type | result | used for |
|---|---|---|
| relevance | `{score ∈ [0,1]}` | relevance signal |
| intent | `{label ∈ transactional / commercial_investigation / informational / navigational, score ∈ [0,1]}` | intent signal (score = purchase-intent strength) and label |
| entity | `{label ∈ none / brand / author / trademark / product_line / other, entity}` | brand/author/trademark families are excluded from backend packing and from listing recommendations |
| equivalence | `{equivalent: bool}` | family links |

`parse_judgment` re-validates every field and **recomputes the input
hash**. ResearchRun stores every returned judgment *before* parsing it.
Records that fail parsing, or answer a request that was never made, are
listed under `invalid_judgments` and ignored. Unanswered requests fall
back explicitly.

`JudgmentProvider.judge(requests, *, marketplace, run_id) -> list[Evidence]`.
`FixtureJudgmentProvider` reads a fixture `judgments` block (model,
`prompt_versions`, and per-market answers keyed by keyword or `"a || b"`).
A rationale is required.

**Signal sources.** Each `SignalDerivation` records a source for every
signal:
* `evidence`: demand, competition, coverage;
* `judgment`: relevance or intent from a valid judgment, citing its
  evidence ID;
* `heuristic`: the v0.3 fallback, with no evidence, so `score_keyword`
  flags it.

Reports mark each relevance or intent contribution **J** (judgment) or
**H** (heuristic).

### Review themes (`reviews/themes.py`)

Theme Evidence (`kind = "review_theme"`) payload:
`theme, polarity (positive/negative/mixed/neutral), review_evidence_ids,
products, count, terms, extractor, extractor_version, rationale`.
`review_theme_evidence` derives `products` and `count` from the actual
review evidence. `parse_review_theme` re-derives them, so a theme can't
overstate its support or cite reviews that aren't stored.

`ReviewThemeProvider.themes(reviews, *, marketplace, run_id)` receives the
run's **stored** review evidence. In v0.4a, `FixtureReviewThemeProvider`
resolves precomputed themes, which cite reviews as `"ASIN/index"`. It runs
inside the `competitor_reviews` task, right after reviews are stored.

`summarize_review_themes` (deterministic) produces:
* **repeated positives** and **repeated complaints**: count ≥
  `min_theme_count` (2);
* everything else;
* **listing opportunities**, from repeated competitor complaints and
  praise.

Opportunities are phrased conditionally ("only if the product genuinely
avoids this problem", "if the product offers this"). The single exception
is when one of the theme's terms appears in
`ProductInput.attributes["features"]`; the opportunity then quotes that
first-party input verbatim. Themes only about our own product are never
presented as competitive opportunities. No claim about our product is
generated from competitor evidence.

## Live semantic providers (v0.4b)

`semantic/` adds LLM-backed implementations of the v0.4a contracts. CI
stays offline, and every result stays reproducible and auditable.

```
LLMJudgmentProvider / LLMReviewThemeProvider
   │  versioned prompt template (semantic/prompts/*.toml, lock.json)
   │  structured output: output_config.format = JSON schema
   ▼
 cache lookup ──hit──▶ rebuilt from the cached exchange, re-validated
   │ miss
 budget check (live transports only) ──refused──▶ stop the batch; heuristics fill in
   ▼
 Transport: AnthropicTransport (live) | ReplayTransport | ScriptedTransport
   │           └ RecordingTransport wraps any transport and saves exchanges
   ▼
 semantic_call Evidence (full request + normalized response)
   ▼
 validation: judgment_evidence + parse_judgment / review_theme_evidence
   ▼
 judgment / review_theme Evidence (+ call metadata), cached only if valid
```

### Live vs replay vs scripted

| Transport | Network | Counts as live | Use |
|---|---|---|---|
| `AnthropicTransport` | yes, official `anthropic` SDK (optional extra `atlas-amazon[llm]`), lazily imported | yes | real runs; **disabled unless `ATLAS_ALLOW_LIVE_LLM=1`** (or `allow_live=True`) |
| `RecordingTransport(inner, path)` | as inner | as inner | capture a live run for later replay |
| `ReplayTransport(path)` | **never** | no | CI and local reproduction; an unrecorded request is a `replay_miss` (unanswered, never invented) |
| `ScriptedTransport(fn)` | never | configurable | tests; `semantic/synthetic.py` scripts answers from fixture judgments for **synthetic** demo recordings |

Default request:
* model `claude-opus-5-5`, effort `low` (classification), thinking left
  to the model (adaptive);
* `output_config.format` JSON schema;
* server-side refusal fallback (`betas: ["server-side-fallback-2026-07-01"]`,
  `fallbacks: "default"`).

The served model is recorded separately from the requested one. A
`refusal` stop reason yields no judgment. Replaying a recorded run
reproduces the original evidence **byte for byte**: identical
content-addressed IDs and timestamps from the original response.

### Prompt versioning

Each template has a `version` (e.g. `relevance-v1`) that is recorded on
every judgment, cache key and `semantic_call`.
`semantic/prompts/lock.json` pins each version's fingerprint, a sha256 of
system + user + JSON schema + max_tokens. Editing a template without
bumping its version fails `test_templates_match_lock_file`. The user
template has exactly one placeholder, `{input_json}`, rendered as sorted
JSON inside `<input>` tags.

### Cache

`SemanticCache(path)` is append-only, checksummed JSONL. An entry is
reused only if **kind, input hash, provider, model and prompt version all
match**, and the stored prompt fingerprint equals the current one;
otherwise it is a *stale* miss. Entries store the raw exchange (request
plus response), never a verdict. A hit goes through exactly the same
validation as a live response, and only validated exchanges are cached.

### Cost and usage controls

`UsageLedger` records one `UsageRecord` per request: provider, served
model, purpose, prompt version, source (live / cache / replay / skipped),
outcome (ok / malformed / refusal / replay_miss / error / budget), input
and output tokens and estimated cost.

`SemanticBudget(max_live_calls=, max_cost_usd=)` is enforced per run,
**before** each live call:
* the call limit refuses the next call once the limit is reached;
* the cost limit requires `spent + worst case of the next call` (estimated
  input plus the full `max_tokens` output) ≤ limit;
* an unpriced model can't be bounded, so it is refused.

A refusal stops the batch. Unanswered requests fall back to the explicit
heuristics, and the halt appears in the report.

`PricingTable` holds list prices as of 2026-09-25 and can be overridden.
Costs are *estimates*. `ResearchResult.semantic_usage` and the report's
"Semantic usage" section summarize live calls, replays, cache hits, tokens,
estimated cost, failures and halts. `estimate_recording_cost(path, model)`
prices a recorded run offline: an expected figure (thinking tokens
excluded) and a worst case.

### Human overrides

`HumanJudgmentProvider` records reviewer decisions as ordinary judgment
Evidence: `provider = "human"`, `model = "human:<reviewer>"`,
`prompt_version = "human-review-v1"`, with a rationale required.
`ResearchProviders(human_judgments=...)` runs alongside the model provider.
`resolve_judgments` pairs model and human judgments per (type, input hash),
and **the human judgment wins**. Both records are stored.

The report's *Human overrides* table shows the model judgment, the human
judgment and which one was used. Signal sources are `human` (mark **R**),
`judgment` (**J**, model), `heuristic` (**H**) or `evidence`.

### Evaluation

`evaluate_judgments(candidate, reference)` compares model judgments (live
or replayed) against reference judgments (the fixtures), **per type, with
no combined score**:
* relevance: share with |Δscore| ≤ 0.2, plus mean absolute error;
* intent: label agreement, plus score mean absolute error;
* entity: label agreement, plus blocking-decision agreement;
* equivalence: agreement.

Missing and candidate-only answers are counted separately. Every
disagreement lists both values and both rationales.
`render_evaluation_markdown` formats the report. See
`docs/examples/evaluation_*.md`; those use **synthetic** recordings.

### Configuration and security

* Credentials come only from the environment or an `ant auth login`
  profile, resolved by the SDK. atlas never reads, stores or logs them.
* Live calls require an explicit opt-in (`ATLAS_ALLOW_LIVE_LLM=1`). The
  test suite clears that flag and makes `anthropic` unimportable.
* `ensure_no_secrets` refuses to write credential-shaped content (API-key
  patterns, bearer tokens, auth headers or fields) to recordings, caches or
  `semantic_call` evidence. A repository-wide test scans every committed
  text file.
* Local caches and live recordings are git-ignored (`.atlas/`,
  `*.semantic-cache.jsonl`, `*.recording.local.jsonl`). Commit only
  reviewed fixtures.

## Roadmap

1. **v0.1**: local domain core and tests.
   **v0.1.1**: rule-source verification pass (2026-10-03).
2. **v0.2**: decomposable keyword scoring, the evidence
   store Protocol plus in-memory and append-only JSONL stores, provider
   Protocols with fixture fakes, and the Proposal model with audit-gated
   validation.
3. **v0.3**: the offline `ResearchRun`: priority-driven collection,
   evidence-derived signals with explicit missing data, ranking, audit,
   backend proposal, gap and placement recommendations, validated
   proposals, and a human-review report.
4. **v0.4a**: offline semantic layer. Keyword families with
   explained links; the `JudgmentProvider` contract (relevance, intent,
   entity, equivalence) with a fixture fake; judgment-sourced
   relevance/intent with an explicit heuristic fallback; entity-flag
   exclusions; review-theme evidence and summaries with conditional,
   first-party-grounded listing opportunities.
5. **v0.4b (this release)**: live semantic providers. LLM judgments and
   review themes through the official SDK (opt-in), versioned prompts,
   a persistent cache, record/replay for offline CI, a usage ledger with
   hard call and cost limits, human overrides, and per-type evaluation.
6. **v0.5 (recommended)**: a real recorded baseline and review workflow:
   * record one live run per scenario (with approval for the spend) and
     publish real per-type agreement and measured cost;
   * an override file workflow: export disagreements for a reviewer and
     import their decisions as human judgments;
   * request batching or Batch API support to cut semantic cost;
   * then the first read-only live market-data adapter (autocomplete or
     SP-API Catalog) with the same record/replay discipline.
7. **Later**: a minimal CLI, read-only live adapters (autocomplete, SP-API
   Catalog, Product Type Definitions), LLM copy generation with
   deterministic re-validation, an approval-gated write path, more recipes,
   and a multi-marketplace rules matrix.
