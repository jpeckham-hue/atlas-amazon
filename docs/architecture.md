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

`✓` = exists (v0.2), `·` = planned.

```
atlas-amazon/
├── .gitattributes                 ✓ LF normalization for Windows/Linux
├── pyproject.toml                 ✓ hatchling; no runtime deps; pytest + ruff dev
├── README.md                      ✓
├── docs/
│   ├── architecture.md            ✓ this file
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
│   │   └── scoring.py             ✓ decomposable keyword score, ranking, signal transforms
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
│   │   └── proposal.py            ✓ Proposal, ProposalBasis, validate_proposal
│   ├── research/                  · v0.3 offline research run + review report
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

## Roadmap

1. **v0.1**: local domain core and tests.
   **v0.1.1**: rule-source verification pass (2026-10-03).
2. **v0.2 (this release)**: decomposable keyword scoring, the evidence
   store Protocol plus in-memory and append-only JSONL stores, provider
   Protocols with fixture fakes, and the Proposal model with audit-gated
   validation.
3. **v0.3**: offline research orchestration. A `ResearchRun` drives the
   providers in `research.priorities` order into the evidence store, derives
   `KeywordSignals` from stored evidence (keyword candidates from
   suggestions and metrics, demand/competition from metrics, competitor
   coverage from catalog evidence), ranks keywords, audits the current
   listing, emits deterministic heuristic proposals (e.g. backend packing),
   and writes a human-review report that links every number to evidence.
   Fully fixture-driven and offline. The CLI waits until the run shape has
   settled.
4. **v0.4**: first live read-only providers (autocomplete, SP-API catalog, and
   SP-API Product Type Definitions to verify per-product-type limits for
   bullets, description and generic keywords), then LLM generation and
   relevance/intent judgments with deterministic re-validation.
5. **Later**: an approval-gated SP-API write path, more category recipes, and
   a multi-marketplace rules matrix.
