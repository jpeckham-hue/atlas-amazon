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
 providers  SP-API · keyword/market data (e.g. Nexscope) · autocomplete · reviews
 (planned)  each implements a narrow Protocol and returns Evidence records
                            ▼
 evidence   Evidence(id, kind, provider, marketplace, retrieved_at, payload, url)
            append-only store; recommendations reference evidence ids
                            ▼
 domain     recipes ─▶ keyword engine ─▶ coverage ─▶ audit ─▶ planner
 (pure)     all deterministic and side-effect free; v0.1 implements the
            parts marked ✓ in the file tree below
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

`✓` = exists in v0.1, `·` = planned.

```
atlas-amazon/
├── .gitattributes                 ✓ LF normalization for Windows/Linux
├── pyproject.toml                 ✓ hatchling; no runtime deps; pytest + ruff dev
├── README.md                      ✓
├── docs/
│   ├── architecture.md            ✓ this file
│   └── rule-sources.md            ✓ verified / unverified / heuristic rule inventory
├── src/atlas_amazon/
│   ├── models.py                  ✓ ProductInput, Listing, Evidence, SourceRef, Finding, AuditReport
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
│   │   └── scoring.py             · decomposable keyword score (see Scoring)
│   ├── backend/
│   │   └── packing.py             ✓ byte-budget and slot packing with exclusion reasons
│   ├── audit/
│   │   └── listing.py             ✓ field limits, required fields, rule checks registry
│   ├── evidence/                  · store interface + local JSONL/SQLite implementation
│   ├── providers/                 · Protocols + fixtures-backed fakes, then live adapters
│   │   ├── base.py                ·   KeywordDataProvider, CatalogProvider, ReviewProvider, ...
│   │   ├── sp_api.py              ·
│   │   ├── autocomplete.py        ·
│   │   └── nexscope.py            ·
│   ├── planner/                   · proposal model (field, value, evidence_ids, rationale)
│   ├── llm/                       · prompt contracts; outputs re-validated
│   └── review/                    · approval records; publish is gated on approval
└── tests/                         ✓ one module per domain module
```

## Domain model

| Model | Purpose |
|---|---|
| `ProductInput` | User-supplied metadata, recipe id, marketplace, optional ASIN and competitor ASINs (validated format, no self-competition). |
| `Listing` | Recipe-agnostic `field -> str \| tuple[str]` map. The recipe decides what the fields mean. |
| `Evidence` | One observed fact. `retrieved_at` must be timezone-aware. The payload is frozen. |
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

## Deterministic utilities (v0.1)

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

## Scoring

No score in atlas-amazon is a black box. The keyword score (planned for
`keywords/scoring.py`) is:

```
score(k) = Σ_s  w_s · x_s(k)        s ∈ {relevance, demand, competition′, intent, competitor_coverage}
```

* Each `x_s ∈ [0, 1]` comes from a documented transform of evidence. For
  example, demand might be `log1p(volume) / log1p(max volume in the candidate
  set)`, and `competition′ = 1 − competition`.
* The `w_s` come from the recipe and sum to 1.
* The result keeps each `w_s · x_s` contribution and the evidence ids behind
  each `x_s`.
* Where a signal comes from an LLM (relevance, intent), its value is recorded
  as evidence too (model, prompt version, timestamp), so it can be audited
  and reproduced.

## Providers (planned)

Each provider implements a narrow `typing.Protocol` and returns `Evidence`:

| Protocol | Candidates | Evidence kinds |
|---|---|---|
| `CatalogProvider` | Amazon SP-API (Catalog Items, Listings Items) | `catalog_item`, `competitor_listing` |
| `KeywordDataProvider` | Nexscope or similar | `keyword_metric` |
| `SuggestionProvider` | Amazon autocomplete | `autocomplete_suggestion` |
| `ReviewProvider` | Review data vendors | `review_sample`, `review_theme` |
| `ListingWriter` | SP-API Listings Items (patch) | Only callable with an approval record |

Each provider ships with a fixtures-backed fake first. Live adapters come
later, behind configuration, with rate limiting and raw-response capture.

## Roadmap

1. **v0.1**: local domain core and tests.
   **v0.1.1**: rule-source verification pass (2026-10-03).
2. **v0.2**: decomposable keyword scoring, a local evidence store (JSONL or
   SQLite), provider Protocols with fixture fakes, and a planner `Proposal`
   model that links to evidence ids.
3. **v0.3**: research orchestration driven by `research.priorities`, a CLI,
   and an end-to-end offline run that ends in a human-review report.
4. **v0.4**: first live read-only providers (autocomplete, SP-API catalog, and
   SP-API Product Type Definitions to verify per-product-type limits for
   bullets, description and generic keywords),
   then LLM generation with deterministic re-validation.
5. **Later**: an approval-gated SP-API write path, more category recipes, and
   a multi-marketplace rules matrix.
