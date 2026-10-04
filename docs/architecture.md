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

`✓` = exists (v0.9), `·` = planned.

```
atlas-amazon/
├── .gitattributes                 ✓ LF normalization for Windows/Linux
├── pyproject.toml                 ✓ hatchling; no runtime deps; pytest + ruff dev
├── README.md                      ✓
├── docs/
│   ├── architecture.md            ✓ this file
│   ├── baselines/                 ✓ live baselines (v0.6 frozen, v0.7) and v0.8 calibration
│   ├── reviews/                   ✓ human review queue for disputed reference judgments
│   ├── benchmarks/                ✓ semantic cost benchmark (v0.4b vs v0.5), golden
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
│   │   ├── contract.py            ✓ JudgmentRequest, judgment Evidence, parse_judgment
│   │   └── context.py             ✓ first-party product context for judgments (v0.7)
│   ├── semantic/
│   │   ├── prompts/*.toml         ✓ versioned prompt templates + lock.json fingerprints
│   │   ├── prompts/history/       ✓ archived prompt versions, loadable for replay
│   │   ├── batched.py             ✓ BatchedJudgmentProvider (v0.5 default): batch, escalate
│   │   ├── batch.py               ✓ item IDs, batch prompt input, per-item response parsing
│   │   ├── tiers.py               ✓ LLMSettings, fast / strong model tiers
│   │   ├── escalation.py          ✓ EscalationPolicy: when the strong tier is asked
│   │   ├── budgets.py             ✓ schema-derived output token budgets
│   │   ├── plan.py                ✓ SemanticCallPlan / RunSemanticPlan, expected + worst cost
│   │   ├── deterministic.py       ✓ RuleJudgmentProvider: questions plain code answers
│   │   ├── benchmark.py           ✓ v0.4b vs v0.5 comparison from recordings
│   │   ├── comparison.py          ✓ strong-tier comparison (evaluation only)
│   │   ├── recorded.py            ✓ judgments re-validated from old recordings
│   │   ├── review.py              ✓ human review decisions superseding references
│   │   ├── strategies.py          ✓ offline routing-strategy simulation and pricing
│   │   ├── llm.py                 ✓ LLMJudgmentProvider (one call each), LLMReviewThemeProvider
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
 Transport: GatewayTransport (live, default) | AnthropicTransport (live, optional)
            | ReplayTransport | ScriptedTransport
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
| `GatewayTransport` (default, `default_live_transport()`) | yes, Vercel AI Gateway's Anthropic-compatible Messages API (`https://ai-gateway.vercel.sh`) via the official `anthropic` SDK (optional extra `atlas-amazon[llm]`), lazily imported; auth `AI_GATEWAY_API_KEY` or `VERCEL_OIDC_TOKEN`; a request's `providerOptions` is sent as a body field | yes | real runs; **disabled unless `ATLAS_ALLOW_LIVE_LLM=1`** (or `allow_live=True`) |
| `AnthropicTransport` (optional) | yes, direct Anthropic API, credentials resolved by the SDK; refuses gateway-only `providerOptions` | yes | direct runs with the `DIRECT_*` tiers; same opt-in |
| `RecordingTransport(inner, path)` | as inner | as inner | capture a live run for later replay |
| `ReplayTransport(path)` | **never** | no | CI and local reproduction; an unrecorded request is a `replay_miss` (unanswered, never invented) |
| `ScriptedTransport(fn)` | never | configurable | tests; `semantic/synthetic.py` scripts answers from fixture judgments for **synthetic** demo recordings |

Request settings come from `LLMSettings` (see *Model tiers* under v0.5):
model, optional `effort`, optional `thinking`, optional server-side refusal
fallback (`betas: ["server-side-fallback-2026-07-01"]`,
`fallbacks: "default"`) and a thinking allowance added to `max_tokens` for
models that always think. Every request uses `output_config.format` with a
JSON schema. In v0.4b the default was Claude Opus 5.5 with 4,096 output
tokens per judgment; v0.5 replaced both (below).

The served model is recorded separately from the requested one. A
`refusal` stop reason yields no judgment. Replaying a recorded run
reproduces the original evidence **byte for byte**: identical
content-addressed IDs and timestamps from the original response.

### Prompt versioning

Each template has a `version` (e.g. `relevance-v2`) that is recorded on
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

`UsageLedger` records one `UsageRecord` per API call, cache hit or skipped
call: provider, served model, purpose, prompt version, source (live / cache
/ replay / skipped), outcome (ok / partial / malformed / refusal /
replay_miss / error / budget), tier, items in the call, valid items,
escalated items, item-level failures, input and output tokens and estimated
cost.

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
`ResearchProviders(human_judgments=...)` is asked **first** (v0.5): a request
with a valid human answer is removed before any rule, cache lookup or model
batch, so it costs nothing. `resolve_judgments` still pairs model and human
judgments per (type, input hash) and **the human judgment wins** wherever
both exist (for example evidence stored by an earlier version).

The report's *Human overrides* table shows the human judgment, the model
judgment if one exists ("not asked" otherwise) and which one was used. Signal sources are `human` (mark **R**),
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

* Live calls use the Vercel AI Gateway credential (`AI_GATEWAY_API_KEY`,
  or `VERCEL_OIDC_TOKEN`), read from the environment when the client is
  created and passed to the SDK; it is never stored on the transport,
  logged, recorded or put in evidence. The optional direct transport's
  credentials come only from the environment or an `ant auth login`
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

## Semantic cost and call efficiency (v0.5)

Same semantic capability, far fewer calls, a bounded worst case. The
judgment contract, Evidence model, validation, replay and human overrides
are unchanged; what changed is how requests reach a model.

```
JudgmentRequests of one stage (equivalence, or keyword relevance/intent/entity)
   │
   ├─ human reviewer decisions ──answered──▶ judgment Evidence (provider "human")
   ├─ deterministic rules ───────answered──▶ judgment Evidence (provider "rules")
   ├─ not needed (relevance/intent of a family that cannot be ranked) ──▶ skipped
   ▼
 BatchedJudgmentProvider
   ├─ per-judgment cache (strong tier, then fast tier) ──hit──▶ rebuilt + re-validated
   ├─ plan: fast batches, certain escalations, escalation reserve, costs
   ├─ fast-tier batches (Claude Haiku 4.5), parsed by item ID, item by item
   ├─ escalation policy ──flagged──▶ strong-tier batches (Claude Sonnet 5.5)
   ▼
 one judgment Evidence per request, each citing its batch's semantic_call
```

### Call routing (`research/run.py`)

`ResearchRun._judge` routes each stage's requests cheapest first: human
decisions, then `RuleJudgmentProvider`, then the model provider with what
is left. Relevance and intent are requested only for families that can be
ranked (all evidence signals present); entity is still requested for every
family because it guards the backend and recommendations. Both behaviors
can be turned off (`ResearchConfig(deterministic_judgments=False,
skip_unrankable_judgments=False)`), which reproduces v0.4b's request set.

### Deterministic judgments (`semantic/deterministic.py`)

Only what plain code settles with certainty, as ordinary judgment Evidence
(`provider "rules"`, `model "rules:<rule>"`, `prompt_version
"deterministic-v1"`, confidence 1.0):

* `recipe_known_entity`: the keyword contains a term the recipe lists under
  `[entities]` (book: `kindle unlimited`, `kdp select` as `trademark`,
  sourced to KDP's keyword guidance);
* `own_title_words`: every content word (ignoring connecting words,
  numbers and units) is in the seller's own product title, which the entity
  prompt itself defines as not another company's entity.

Already deterministic before v0.5 and never sent to a model: limits, byte
counting, normalization and plural folding, duplicate detection,
coverage, recipe prohibited terms, and the stopword-variant and
attribute-rotation family links. Relevance and intent have no reliable
rule, so they stay semantic (the term-overlap heuristic remains only an
explicit fallback and an escalation signal).

### Batching (`semantic/batch.py`, `semantic/batched.py`)

* One template, `judgment_batch-v1`, covers all four judgment types; its
  schema is a `results` array whose items are an `anyOf` of the per-type
  shapes (one compiled grammar for every batch).
* Item IDs come from the request (`rel-` + 10 hex of the input hash), never
  from position. Items are sorted by subject, then ID, so a keyword's three
  judgments share a batch and the same requests always render the same
  request (stable replay hashes). The shared product context is hoisted
  into `contexts`; each request's input hash still covers its full input.
* Batches hold at most `BatchSettings.max_items` (default 40) items,
  balanced in size, and are split further if their output budget would
  exceed the template cap (8,192).
* Parsing maps results by ID. Missing, duplicated (all copies rejected),
  mistyped and malformed items fail alone; unknown IDs are ignored and
  reported; order differences are reported but harmless. A refusal or an
  unparseable response fails the whole batch. Item failures are counted
  per call in the usage ledger.
* Each valid item becomes its own judgment Evidence: its own input hash,
  result, confidence, rationale, served model, prompt version and evidence
  ID, with `call` metadata naming the batch's `semantic_call` evidence, the
  item ID, batch size, tier and (if escalated) the escalation record.
* The cache stays per judgment, keyed as before (type, input hash,
  provider, model, prompt version). The batch exchange is stored once and
  referenced by request hash, so a later batch with different neighbours
  still reuses each cached item.

### Model tiers (`semantic/tiers.py`)

| Tier | Default | Request settings | Used for |
|---|---|---|---|
| fast | `anthropic/claude-haiku-4.5` ($1 / $5 per MTok) | no `effort` (Haiku 4.5 rejects it), no thinking, no fallbacks | every batched judgment |
| strong | `anthropic/claude-sonnet-5.5` ($2 / $10) | `effort: low`, `thinking: {"type": "between_tools"}` (no extended thinking), no fallbacks (`between_tools` is Sonnet-5.5-only) | escalated items; review themes |
| `OPUS_STRONG` (optional) | `anthropic/claude-opus-5.5` ($4 / $20) | `effort: low`, 2,048-token thinking allowance (Opus 5.5 always thinks) | when a stronger strong tier is wanted |

Model IDs are Vercel AI Gateway IDs, and every gateway tier sends
`providerOptions: {"gateway": {"only": ["anthropic"]}}`, so Anthropic's own
API serves the request: prices are Anthropic list prices (the gateway catalog
shows the same, read 2026-10-04) and Anthropic-specific request fields keep
their meaning. The pin is part of the recorded, hashed request. Responses
report provider-qualified served models (for example
`anthropic/claude-haiku-4.5`), and `semantic_call` evidence records the
transport (`vercel-ai-gateway`). `DIRECT_FAST`, `DIRECT_STRONG` and
`DIRECT_OPUS_STRONG` (with Anthropic's server-side refusal fallback) are the
same settings for the direct transport.

`ModelTiers(fast=..., strong=...)` makes both configurable. Every judgment
records the served model (`model`), the requested model and the tier.
Whether Haiku 4.5 is good enough per judgment type is an empirical question
for `evaluate_judgments` once live recordings exist; nothing here claims it.

### Escalation (`semantic/escalation.py`)

Only flagged items go to the strong tier, never everything:

| Reason | Rule |
|---|---|
| `failed` | no usable fast answer (missing, duplicate, mistyped, malformed, refused or unparseable batch) |
| `low_confidence` | confidence < 0.5 |
| `ambiguous_equivalence` | equivalence confidence < 0.7 (family grouping would ignore it anyway) |
| `heuristic_disagreement` | relevance differs from the term-overlap heuristic by ≥ 0.7 **and** confidence < 0.8 |

At most `max_escalations` (default 12) items per stage escalate. The strong
model gets the same batch prompt and never sees the fast answer. Its valid
answer replaces the fast one; if it fails, a valid fast answer is kept.
The strong judgment's `call.escalation` records the reason, the fast
model, its answer, confidence and `semantic_call`. Transport errors and
replay misses are not escalated.

### Output budgets (`semantic/budgets.py`)

v0.4b allowed 4,096 output tokens per judgment, and cost guards priced every
call at that, so the worst case was ~38x the expected cost. Budgets are now
derived from the response schema: per item, the longest valid item with an
empty rationale (counted at a conservative 3 chars per token) plus 130
rationale tokens (prompts ask for at most 25 words) plus 20 for an entity
name; per batch, the sum plus 24. Individual templates use 256. Review
themes get 24 + 8 themes x 180 + 8 tokens per review, capped at 4,096.
`tests/test_semantic_budgets.py` checks that maximal valid answers fit.

### Call plans (`semantic/plan.py`)

`BatchedJudgmentProvider.plan(requests)` and
`ResearchRun.plan_semantics()` show, before any live call: requests,
human / rules / skipped / cache-hit counts, live items, each planned call
(tier, model, items by type, `max_tokens`, estimated input tokens,
expected and worst-case cost, exact request hash), certain escalations,
the escalation reserve, and planned / expected / worst-case call counts.
Execution follows the plan: the planned fast batches are exactly the
requests sent. `plan_semantics()` plans the keyword stage on families
before equivalence merges, an upper bound. Plans executed in a run are in
`ResearchResult.semantic_plans` and the report's *Semantic call plan*.

### Usage and cost accounting

`SemanticUsageSummary` reports API calls (live and replayed), fast and
strong calls, escalated items, model judgments, cache hits, human and
deterministic answers, skipped requests, tokens, planned expected and
worst-case cost, measured cost (API-reported tokens of live calls only)
and cost per judgment. Without live calls nothing is reported as measured.

### Benchmark (`semantic/benchmark.py`)

`docs/benchmarks/semantic_cost_v0.5.md` compares v0.4b (the committed v0.4b
recordings in `tests/fixtures/recordings/v04b/`) with v0.5 (the current
synthetic recordings and plans), and checks that individual and batched
execution give the same ranking, entity flags, proposals, recommendations
and families. All figures are estimates from synthetic recordings.

## Live semantic baseline (v0.6)

One live run per example scenario, through Vercel AI Gateway (routed to
Anthropic), with the unchanged v0.5 pipeline and tiers. Recorded with
`scripts/record_live_baseline.py` under hard caps (10 calls per scenario,
$0.25 combined, stop before any call that could exceed the remaining
budget). The recordings in `tests/fixtures/recordings/live/` are real and
labeled as such (`synthetic: false`, `transport: vercel-ai-gateway`);
`tests/test_live_baseline.py` replays them with sockets disabled and
regenerates [docs/baselines/live_v0.6.md](baselines/live_v0.6.md). A
one-call strong-tier probe (`gateway_strong_probe.jsonl`, $0.0005) first
confirmed that the gateway accepts Sonnet 5.5's `between_tools` thinking.

**Measured** (API-reported tokens times list price):

| | book | product | total |
|---|---|---|---|
| API calls (fast / strong) | 3 (2 / 1) | 5 (3 / 2) | 8 |
| Escalations / cache hits | 0 / 0 | 2 / 0 | 2 / 0 |
| Input / output tokens | 6,755 / 2,392 | 11,602 / 3,049 | 18,357 / 5,441 |
| Cost | $0.0225 | $0.0332 | **$0.0557** |
| Plan: expected / worst case | $0.0229 / $0.0858 | $0.0286 / $0.0987 | $0.0515 / $0.1846 |

Agreement with the fixture judgments (per type; every disagreement with both
rationales is in the baseline report):

| | relevance | intent | entity (label / blocking) | equivalence |
|---|---|---|---|---|
| book | 8/11 | 1/4 | 2/3 / 100% | 1/1 |
| product | 10/12 | 3/5 | 6/6 / 100% | 2/2 |

**What the baseline validates**

* Cost and call count: 8 calls against 7 planned (one escalation batch), and
  measured cost within 8% of the plan's expected figure.
* Output budgets: calls used 24-53% of their computed `max_tokens`; nothing
  was truncated.
* ID-matched batching with failure escalation: in one 23-item batch the fast
  model ended normally but silently left out 2 items (relevance and intent
  for "insulated water bottle"). Matching by item ID caught the omission, the
  `failed` rule escalated both, and the strong tier answered them. Matching by
  position would have silently mislabeled them.
* Structure: keyword families, rejected pairs and the set of entity-blocked
  keywords match the fixture runs exactly, and the backend proposals still
  pass the audit.

**What it challenges**

* Confidence-based escalation was inert. Fast-tier confidences ranged from 0.60
  to 0.99 and none fell below 0.5, so `low_confidence` never fired, and
  `heuristic_disagreement` (which also needs confidence < 0.8) never did
  either. Every disagreement with the fixtures came at high confidence: the
  fast model's self-reported confidence is not a useful escalation signal.
* Intent is systematically inflated: 21 of 29 live intent labels are
  `transactional`, including genre and category browsing queries ("cozy
  mystery", "water bottle") that the fixtures label
  `commercial_investigation`.
* Relevance is penalized for features the judgment context does not contain.
  The context sends only the product title and seed keywords, so features
  such as "leak proof lid" or "double wall vacuum insulation" (in the
  product's feature list) read as unknown: "not stated in product title or
  seeds". That is an input-design limit, not necessarily a model limit.
* Rankings and recommendations changed materially: in the book, "harbor town"
  rises from 13th to 10th and is now recommended; in the product, "double wall
  vacuum" falls from 3rd to 7th, and the gap list swaps kids/straw phrases for
  attribute phrases (vacuum insulation, double wall, bpa free). Part of this
  is the live model answering keywords the fixtures never covered.
* Review themes match in substance, but one opportunity ("keeps drinks cold")
  lost its first-party support because the deterministic matcher depends on
  the theme's wording.

## Semantic quality: context and risk-based escalation (v0.7)

### First-party product context (`judgments/context.py`)

Keyword judgments (relevance, intent, entity) now receive
`product_context(product, listing, recipe, seeds)`: title, seeds, category
(recipe id), subtitle (books), brand / author when supplied, the seller's
features (product attributes, else listing bullets; at most 10) and the
listing description (at most 500 characters, cut at a word boundary with
`description_truncated: true`). Competitor catalog data, reviews and themes
are never included. Empty fields are omitted. The batch prompt hoists one
shared context per batch, so the extra context costs input tokens once per
call (book input tokens went from 6,755 to 12,225 for the production calls).
`ResearchConfig(product_context=False)` reproduces the v0.6 context.

The context is part of each request's input, so input hashes, cache keys
and replay hashes change with it: old cache entries simply miss. Prompts
moved to `judgment_batch-v2` (and `relevance-v3`, `intent-v3`, `entity-v3`):
stated context is fact, unstated features are unknown, and intent gets
neutral browse-vs-buy guidance.

### Risk-signal escalation (`semantic/escalation.py`)

Confidence is kept as metadata only. Escalation reasons: `failed`,
`feature_underrated`, `lexical_disagreement` (relevance vs a feature-aware
lexical baseline), `intent_structure` (`transactional` for a generic head
term or bare attribute), `entity_conflict` (the seller's own metadata
flagged as an entity), `equivalence_conflict` (contradicts the head-noun
rule), and `low_confidence_with_risk` (low confidence plus a weaker lexical
gap; never low confidence alone). Each escalated judgment records the reason
and the fast answer.

### Strong-tier comparison (`semantic/comparison.py`)

`BatchedJudgmentProvider(..., evaluation="strong_only")` sends every item to
the strong tier, never escalates, and refuses to serve a `ResearchRun`.
`run_strong_comparison` asks it the same judgments the production pipeline
answered, under a separate provider name (`anthropic-strong-eval`), so strong
answers are kept apart and never overwrite production ones.
`evaluate_tier_comparison` scores production and strong tier against the
same reference separately, plus a head-to-head.

### Reading old recordings (`semantic/recorded.py`)

v0.6 requests no longer replay through the v0.7 pipeline (their hashes
changed). `recorded_judgments` rebuilds and re-validates every judgment in a
batch recording (each item's input is reconstructed and must match its ID),
so v0.6 results stay comparable; the documented v0.6 agreement is reproduced
from the raw recordings in `tests/test_live_baseline_v06.py`.

### Live re-measurement

One capped live run per scenario plus a relevance and intent strong-tier
comparison, through Vercel AI Gateway (production runs first, comparisons
only within the remaining budget). A first attempt stalled at the gateway
before any response and was billed nothing (confirmed by the gateway credit
balance); `GatewayTransport` now times out after 120 s per attempt with one
retry.

| Measured | book | product | total |
|---|---|---|---|
| Production calls (fast / strong) | 5 (2 / 3) | 5 (3 / 2) | 10 |
| Production cost | $0.0355 | $0.0355 | $0.0710 |
| Strong comparison (calls / items / cost) | 1 / 24 / $0.0270 | 1 / 32 / $0.0336 | $0.0606 |
| Escalations (reason) | 2 (equivalence_conflict, lexical_disagreement) | 2 (lexical_disagreement x2) | 4 |
| **Total** | $0.0625 | $0.0691 | **$0.1317** |

Agreement with the fixture judgments (agreed / compared):

| | v0.6 live | v0.7 production | v0.7 strong tier |
|---|---|---|---|
| book relevance / intent / entity / equivalence | 8/11, 1/4, 2/3, 1/1 | 8/11, 3/4, 3/3, 1/1 | 9/11, 3/4 (relevance and intent only) |
| product relevance / intent / entity / equivalence | 10/12, 3/5, 6/6, 2/2 | 11/12, 4/5, 6/6, 2/2 | 12/12, 4/5 (relevance and intent only) |

Focus keywords (fixture / v0.6 / v0.7 production / v0.7 strong):
"leak proof" relevance 0.75 / 0.5 / 0.9 / 0.7 and "double wall vacuum"
0.8 / 0.6 / 0.95 / 0.75, both fixed by the stated features; "amateur sleuth"
0.8 / 0.6 / 0.7 / 0.6 (escalated, and the rationale cites the description);
"harbor town" 0.2 / 0.5 / 0.8 / 0.45, now further from the fixture. Intent
bias: live `transactional` labels fell from 21 of 29 to 11 of 29 (the strong
tier: 6 of 29), and the head terms "cozy mystery", "mystery books" and
"water bottle" now agree with the fixtures.

**Findings**

* Product context plus the prompt change made the larger improvement, at
  the production price: the feature keywords were fixed by context, and the
  intent bias (5 more intent agreements were possible; 3 were gained) by the
  intent guidance. The four escalations moved one fixture comparison
  ("amateur sleuth").
* Richer context makes the fast tier over-rate generic and setting terms:
  "small town" 0.3 -> 0.7, "mystery books" 0.6 -> 0.8, "harbor town"
  0.2 -> 0.8. The strong tier stays near the fixture on "small town" and
  "mystery books"; none of the current risk signals catches this. That is
  the strong tier's +1 relevance agreement per scenario.
* Downstream: keyword families, the set of entity-blocked keywords and
  audit-valid proposals are unchanged; every judgment, theme and signal keeps
  its evidence lineage. Rankings and recommendations shift (product: the
  feature keywords move up; book: "small town" and "harbor town" are now
  recommended).
* Review-theme opportunity support still depends on theme wording ("keeps
  contents cold for long periods" lost its support again).
* Single runs cannot separate prompt effects from run-to-run variation;
  the report labels those changes as such.

## Relevance calibration and human-grounded review (v0.8)

All offline; no live calls were made in v0.8.

### Relevance-risk signals (`semantic/escalation.py`)

Richer context made the fast tier over-rate terms that merely appear in the
product text. For relevance >= 0.7, `relevance_risks` checks whether the
keyword is a `setting_term` (head noun is a setting: "small town", "harbor
town"), a `broad_category` (short phrase headed by a category noun:
"mystery books"), a `generic_head_term` (strictly broader than a seed), or
has `incidental_description_support` (supported only by the description:
"stainless steel"). A hit escalates to the strong tier with every applicable
reason recorded; scores are never lowered by formula. A score below the
lexical baseline no longer counts as `lexical_disagreement` for such risky
terms, so the baseline cannot push setting terms back up.

### Human review (`semantic/review.py`)

`docs/reviews/judgment_review_v0.8.md` lists every open fixture/live
disagreement with the first-party context, all judgments (fixture, v0.6,
v0.7 fast, production and strong) and all rationales, plus Claude's
classification (model error, stale reference, ambiguous) and proposal,
clearly marked as not a decision. A reviewer records decisions in
`tests/fixtures/reviews/v08_human_decisions.json`; `load_review_decisions`
turns them into ordinary `human` judgment Evidence and `supersede` makes them
the evaluation reference. Fixture and model judgments are never edited or
deleted.

### Routing strategies, compared offline (`semantic/strategies.py`)

`simulate_strategy` replays recorded fast answers and recorded strong answers
under a routing strategy; `PrecomputedJudgmentProvider` feeds the result to a
real `ResearchRun` for downstream effects; `strategy_cost` prices it with the
planner. `BatchedJudgmentProvider(strong_types={RELEVANCE})` implements the
strong-for-relevance strategy for real use.

| | book relevance (fixture / proposed) | product relevance (fixture / proposed) | strong items | expected / worst cost (judgment stages) |
|---|---|---|---|---|
| v0.7 production | 8/11 / 8/11 | 11/12 / 12/12 | 4 | measured in v0.7 |
| A: risk escalation (v0.8 signals) | 10/11 / 11/11 | 12/12 / 12/12 | 7 | $0.0522 / $0.1543 |
| B: strong tier for all relevance | 10/11 / 11/11 | 12/12 / 12/12 | 28 | $0.0557 / $0.1837 |

Intent, entity and equivalence agreement are identical across strategies.
Strategy A drops "small town" and "harbor town" from the book's
recommendations (the v0.7 failure mode) and leaves the product's unchanged;
strategy B also reorders the product's recommendations. Strategy A is the
default.

### Review-theme feature support (`reviews/themes.py`)

A seller feature supports a theme when a theme term appears in it as a
phrase, when it shares two distinctive words with the theme label and terms
(the product's own title words do not count), or one such word plus a word
recurring across the theme's supporting reviews. Support is still always a
verbatim seller feature; review words alone never create it.

## Intent calibration (v0.9)

All offline; no live calls were made in v0.9.

### Intent separated from relevance (prompts)

`judgment_batch-v3` and `intent-v4` state that intent is what the shopper is
trying to do, judged without regard to this product, while relevance asks
whether that matches this product. A query can be clearly transactional and
still irrelevant ("bottle water": buying bottled water, low relevance to a
reusable bottle); genre and subgenre searches ("small town mystery") are
browsing unless they name a specific title, author, edition or product;
informational is only for information-seeking queries.

The previous versions are archived verbatim in `prompts/history/` and
`load_template(name, version)` loads them, so v0.7 recordings still replay
exactly (`BatchedJudgmentProvider(prompt_version="judgment_batch-v2")`).
The lock pins current and historical versions; cached answers for the old
prompt miss automatically because the prompt version is part of the cache key.

### Intent-risk signals (`semantic/escalation.py`)

When an intent label contradicts the keyword's shape, the judgment goes to
the strong tier for a second opinion (the label is never rewritten):
`genre_browse` (transactional for a genre/subgenre search),
`comparison_shopping` (transactional with "best", "vs", "review", ...),
`generic_plural` (transactional for a short generic plural),
`reordered_product_phrase` (not transactional for a seed's words with a
different head noun, as "bottle water" vs "water bottle"), and
`informational_without_question` (informational with no information-seeking
word). A format word as head ("cozy mystery books") is not a genre search.

Word lists compared with plural-folded head nouns are now folded the same
way (`fold_plural` maps "mystery" to "mysterie"); this also fixes v0.8's
setting and category lists for words ending in -y ("city", "story").

### Routing comparison (offline, from v0.7 recorded answers)

| Human-reviewed reference | v0.8 routing | intent-risk escalation | strong tier for all intent |
|---|---|---|---|
| book intent | 3/4 | **4/4** | 3/4 |
| product intent | 4/5 | 4/5 | 4/5 |
| relevance, entity, equivalence | 11/11, 3/3, 1/1; 12/12, 6/6, 2/2 | unchanged | unchanged |
| strong-tier items (book + product) | 7 | 10 | 36 |
| expected cost, judgment stages | $0.0541 | $0.0562 | $0.0703 |
| worst case | $0.1566 | $0.1566 | $0.1898 |

Intent-risk escalation is the default: it fixes "small town mystery" (the
strong tier agrees with the reviewer) with no ranking, recommendation or
backend change. Strong-for-all-intent also flips "cozy mystery books" to
browsing (against the human decision) and reorders the product's
recommendations. "bottle water" is flagged, but both recorded tiers answered
informational under the v2 prompt, so only the v3 prompt can fix it; that
needs new answers.

### Live confirmation (v0.9 prompt and routing)

One capped production-only run per scenario through Vercel AI Gateway
(`record_live_baseline.py --run --dir v09 --production-only`), recorded in
`tests/fixtures/recordings/live/v09/` and replayed offline by
`tests/test_live_v09.py` (report: [docs/baselines/live_v0.9.md](baselines/live_v0.9.md)).

| Measured | book | product | total |
|---|---|---|---|
| API calls (fast / strong) | 5 (2 / 3) | 5 (3 / 2) | 10 |
| Escalations | 4 (equivalence_conflict, broad_category, setting_term, lexical_disagreement) | 3 (intent_structure, lexical_disagreement, incidental_description_support) | 7 |
| Input / output tokens | 13,064 / 2,930 | 13,360 / 3,284 | 26,424 / 6,214 |
| Cost | $0.0389 | $0.0371 | **$0.0760** |

Agreement with the human-reviewed reference (v0.8 simulated -> v0.9 live):
book relevance 11/11 -> **10/11**, intent 3/4 -> 3/4, entity 3/3, equivalence
1/1; product relevance 12/12 -> 12/12, intent 4/5 -> **5/5**, entity 6/6,
equivalence 2/2.

* Fixed: "bottle water" is transactional 0.8 (the fast tier answered
  transactional; the older head-term rule escalated it needlessly and the
  strong tier confirmed). "small town mystery" is commercial_investigation
  0.7 straight from the fast tier.
* New disagreement: "cozy mystery books" is now browsing (0.7) against the
  reviewer's transactional 0.85. The genre guidance over-corrected: all 13
  book intent labels are commercial_investigation, including "... books"
  queries whose format word signals shopping.
* New disagreement: "cozy mystery kindle unlimited" relevance 0.3 vs the
  (unreviewed) fixture 0.6; the model will not assume Kindle Unlimited
  enrollment the context does not state. The keyword is entity-blocked, so
  no recommendation or backend change follows.
* Downstream: families, entity blocking and audit-valid proposals unchanged;
  review themes equivalent, both product opportunities supported. Book
  recommendations regain "small town" (relevance 0.5, within tolerance of the
  reviewer's 0.3 but below the 0.7 relevance-risk threshold; it rose from 11th
  to 9th when the Kindle Unlimited keyword fell). Product recommendations swap
  "straw lid" for "bpa free" (0.45): neither is a supplied feature;
  recommendations do not yet require first-party support (fixed in the
  closing pass below).

### Closing pass (offline)

Two fixes for the live v0.9 findings, verified by serving the v0.9 live
answers to the current pipeline (`tests/test_v09_closing.py`, report:
[docs/baselines/live_v0.9_closing.md](baselines/live_v0.9_closing.md)).

* **Format-word intent rule** (`semantic/deterministic.py`,
  `format_word_shopping`): a qualified subgenre whose head noun is a product
  format word (book, novel, paperback, hardcover, ebook, audiobook, edition,
  boxset) is a search for products in that subgenre: transactional 0.8,
  answered before the model. A bare genre plus format ("mystery books", a
  broad category) and a genre without a format word ("small town mystery",
  browsing) stay with the model. `ResearchConfig(intent_rules=False)` turns
  it off.
* **Feature-support gate** (`planner/support.py`): a ranked keyword whose
  claimed words are not stated in the seller's first-party information
  (title, subtitle, brand, author, features, description; never seeds) is
  excluded from recommendations and backend terms as `unsupported_by_product`
  and reported in `ResearchResult.unsupported_opportunities` with the
  unsupported terms, the sources checked and its market evidence (family
  sources plus every evidence ID its score cites). It stays ranked. The
  recipe's `[support] claims` sets which words are claims: `descriptors`
  (physical products: every word beyond the product type) or `attributes`
  (books: unit words, "x free"/"x proof"-style compounds and
  "with/without/for" phrases; genre, topic and setting words are relevance
  questions). Book format claims such as "large print" are not yet covered.
  `ResearchConfig(require_feature_support=False)` turns it off.

Against the human-reviewed reference: book intent 3/4 -> **4/4**; book
relevance 10/11, product relevance 12/12 and intent 5/5, entity and
equivalence unchanged. Blocked as unsupported: "bpa free", "straw lid",
"water bottle with straw", "insulated water bottle with straw", "water
bottles for kids" (product) and "cozy mystery with cats" (book); the product's
recommendations lose "bpa free" and its backend proposal loses "bpa free",
"straw" and "kids". Replays and reports of earlier recordings run with
`semantic_helpers.HISTORICAL` (both fixes off) and stay byte-identical.

## Live market data: SP-API Catalog (v0.10)

### Source selection

One source, chosen for supportable access:

* **Amazon search autocomplete: rejected.** It has no official API, and the
  Amazon.com Conditions of Use prohibit "data mining, robots, or similar data
  gathering and extraction tools".
* **Product Advertising API 5.0: unavailable.** Retired (deprecated
  2026-04-30; calls now return 403).
* **SP-API Catalog Items `searchCatalogItems` (2022-04-01): selected.**
  Official and read-only. Auth is Login with Amazon: a refresh token is
  exchanged for a one-hour access token sent as `x-amz-access-token` (no
  SigV4). It needs a registered SP-API application authorized by a seller
  account with catalog access. Rate limit: 5 requests/s, burst 5. No per-call
  fee.
* **What it provides:** for keyword or ASIN queries, the matching catalog items:
  title (`summaries.itemName`), brand, bullet points (`attributes.bullet_point`),
  classifications and sales ranks, per marketplace.
* **What it does not provide:** search volume, conversion, click share or ad
  competition. The result order is the catalog's, not shopper search rank.

### Provider boundary (`providers/sp_api/catalog.py`)

`SpApiCatalogProvider` implements `CatalogProvider.get_items` (identifier
search, 20 ASINs per call) and the new `CatalogSearchProvider.search` (one call
per normalized, de-duplicated keyword query, first page only). It returns only
`Evidence`; raw dicts never leave the module.

* **`catalog_item`** (subject ASIN): `asin`, `title`, `brand`, `bullets`,
  `classifications`, `sales_ranks`, `source` and `raw` (the item as returned).
  The text fields match every other catalog provider, so candidate building
  and coverage read it unchanged.
* **`catalog_search`** (subject: the query): `query`, `keywords`,
  `marketplace_id`, `included_data`, `page_size`, `result_asins` (returned
  order), `number_of_results`, `raw` (the full response).

Every record carries the provider (`sp-api-catalog`), marketplace, run ID, the
original response time as `retrieved_at` and the request URL as `source_url`.
The URL never contains credentials. IDs are content hashes, so replays give
identical IDs.

The provider handles bad and partial input as follows:

* **Marketplace scoping.** Atlas codes map to an SP-API marketplace ID and
  regional endpoint (US is `ATVPDKIKX0DER` on the North America endpoint).
  Items with no summary for that marketplace are skipped, bullets tagged
  with another marketplace are dropped, and unknown marketplaces are refused.
* **Duplicates.** An ASIN returned by several queries is recorded once, and
  the first query wins. It is still listed in each query's `result_asins`.
* **Failures.** Non-200 responses, malformed bodies, transport errors and
  replay misses produce no evidence. Each one is listed in
  `provider.failures` with its reason (for example `http_429 QuotaExceeded`).
  Nothing is invented.

### Transports, record and replay (`providers/sp_api/http.py`)

* **`LiveSpApiTransport`** is the only networked class.
  * It is disabled unless `ATLAS_ALLOW_LIVE_MARKET=1` is set; this is
    separate from the LLM opt-in.
  * It throttles to 5 requests/s and caches the access token in memory.
  * It reads `SP_API_LWA_CLIENT_ID`, `SP_API_LWA_CLIENT_SECRET` and
    `SP_API_REFRESH_TOKEN` from the environment and never stores them.
* **`RecordingHttpTransport`** appends request and response pairs to a
  checksummed, secret-scanned JSONL file. Only the request ID and rate-limit
  headers are kept.
* **`ReplayHttpTransport`** serves responses by exact request hash and
  rejects tampered files.
* **`ScriptedHttpTransport`** is the fake mode used by tests.

CI never sees the network: the tests block sockets.

### Call budget

`max_calls_per_run` is a hard cap on live calls per run ID, checked before
every call. Calls past the cap are recorded as `call_limit` failures and the
reason is added to `provider.halts`. Replays are not counted.
`plan(marketplace=, keywords=, asins=)` returns a `MarketCallPlan` with the
queries, the call count, the rate-limit assumption, the cap and the cost
(expected and worst case are both $0.00). `query_limit` trims the query list
explicitly.

### Research integration (`research/tasks.py`, `research/market.py`)

The optional `ResearchProviders.catalog_search` role runs inside the
`competitor_catalog` task. It searches the run's seed keywords, and the
discovered items join the named competitors as competitor listings. They
feed candidate phrases and competitor-coverage shares only.

* The product's own ASIN, and ASINs already fetched as named competitors,
  are dropped.
* Keyword metrics are untouched: new candidates have no demand data and stay
  unscored on demand.
* While planning semantic calls, a live market provider is not called.
* Without the role, runs, reports and fingerprints are unchanged.

`compare_market(baseline, market, store, provider=)` reports the effect of
market data on a run:

* new candidate keywords;
* fixture candidates confirmed by, or absent from, market listings;
* rank changes and recommendation changes;
* keywords that market data makes tempting but the product does not support.
  These stay `unsupported_by_product` and are never recommended or packed.

Three questions stay separate: market opportunity (what the catalog shows
sellers use), product relevance (the semantic judgments) and product truth
(the seller's own information).

### Live slice (pending access)

`scripts/record_live_market.py` handles the live slice:

* **`--plan`** prints 4 catalog calls: 2 seeds × 2 scenarios, pageSize 10,
  capped at 2 per scenario, plus one token exchange, for $0.00.
* **`--check`** verifies credentials with an LWA token exchange and makes no
  catalog call.
* **`--run`** records to `tests/fixtures/recordings/live/market_v10/`. It
  refuses a non-empty directory and stops after an authorization failure.

At release no SP-API credentials existed, so the slice did not run and no
live recording exists.
[docs/baselines/market_v0.10_synthetic.md](baselines/market_v0.10_synthetic.md)
shows the comparison report on clearly labelled synthetic responses. There,
market listings confirm "bpa free" in 3 of 3 listings, and the keyword stays
blocked.

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
5. **v0.4b**: live semantic providers. LLM judgments and
   review themes through the official SDK (opt-in), versioned prompts,
   a persistent cache, record/replay for offline CI, a usage ledger with
   hard call and cost limits, human overrides, and per-type evaluation.
6. **v0.5**: semantic cost and call efficiency. Human and
   rule answers first, unrankable families skipped, per-judgment cache,
   batched fast-tier calls with ID-matched partial-failure handling,
   selective strong-tier escalation, schema-derived output budgets, call
   plans with expected and worst-case cost, and a v0.4b vs v0.5 benchmark.
7. **v0.6**: live semantic baseline. Vercel AI Gateway as the
   default live transport (`AI_GATEWAY_API_KEY`), one capped live run per
   scenario, real recordings replayed offline in CI, measured cost and
   per-type agreement.
8. **v0.7**: first-party product context for judgments,
   risk-signal escalation, an evaluation-only strong-tier comparison, and a
   live re-measurement ($0.1317).
9. **v0.8**: relevance-risk escalation, a human review queue
   with decisions that supersede stale fixtures, offline routing-strategy
   comparison, and wording-independent review-theme feature support. No live
   spend.
10. **v0.9**: intent separated from relevance in the prompt,
    intent-risk escalation, loadable historical prompt versions, and an
    offline routing comparison against the human-reviewed reference.
11. **v0.10 (this release)**: the first read-only market-data adapter
    (SP-API Catalog Items search) with Evidence conversion, record/replay, a
    hard call cap, competitor-only integration and a market comparison. The
    live slice waits for SP-API access.
12. **Next (recommended)**: provision SP-API access and record the 4-call live
    slice (`scripts/record_live_market.py --run`). Then add one official
    demand source under the same plan / cap / record / replay discipline,
    such as Brand Analytics search terms (needs Brand Registry) or the Amazon
    Ads keyword recommendations, so new catalog candidates can be scored on
    demand. Known small items: book format claims ("large print") are not
    support-checked, and setting terms just below the 0.7 relevance-risk
    threshold can enter the top-N.
13. **Later**: a minimal CLI, more read-only adapters (Product Type
   Definitions), LLM copy generation with
   deterministic re-validation, an approval-gated write path, more recipes,
   and a multi-marketplace rules matrix.
