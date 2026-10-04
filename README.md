# atlas-amazon

An evidence-backed Amazon SEO and listing optimization engine. It supports
books (KDP) first, then general Amazon products through category/product
**recipes**.

Every recommendation should be explainable. The engine records where a fact
came from, which marketplace it applies to and when it was observed. It
records which dated rule a check enforces, and how each score breaks down
into its parts.

> Status: **v0.9: intent calibration.** `ResearchRun` answers
> "which keywords matter, what am I missing, why, and what should change?"
> for a book or a product listing, from fixture data, with every number
> traced to evidence. Semantic judgments (relevance, intent, entity,
> equivalence) and review themes can come from fixtures, from an LLM
> (opt-in, official Anthropic SDK) or from a human reviewer, and every one
> is recorded as hashed, versioned Evidence.
>
> New in v0.9 (offline, no live spend): the prompt separates intent (what the
> shopper is trying to do) from relevance (whether that matches this product);
> intent-risk signals (genre browsing, comparison shopping, generic plurals,
> reordered product phrases, informational labels without a question) send
> suspect intent labels for a second opinion; older prompt versions stay
> loadable so earlier recordings still replay. Against the human-reviewed
> reference, intent-risk escalation raises book intent agreement from 3/4 to
> 4/4 with no other change; see
> [docs/baselines/intent_v0.9.md](docs/baselines/intent_v0.9.md). A live
> confirmation ($0.0760 measured; see
> [docs/baselines/live_v0.9.md](docs/baselines/live_v0.9.md)) fixed both target
> intents ("bottle water" transactional, "small town mystery" browsing) and kept
> product relevance at 12/12, but over-corrected book intent toward browsing
> ("cozy mystery books") and dropped one book relevance (10/11). A closing
> pass (offline, [docs/baselines/live_v0.9_closing.md](docs/baselines/live_v0.9_closing.md))
> answers qualified-subgenre-plus-format queries ("cozy mystery books") as
> transactional by rule (book intent 4/4) and keeps feature keywords the
> seller's own information does not support ("bpa free", "straw lid", "for
> kids") out of recommendations and backend terms, reporting them as
> `unsupported_by_product` market opportunities instead.
>
> In v0.8 (offline, no live spend): relevance-risk signals (setting,
> broad-category, generic and description-only terms) send over-rated
> relevance to the strong tier; a review queue and decision file let a human
> supersede stale fixture judgments without deleting any history; routing
> strategies are compared offline from recorded answers (risk escalation
> matched strong-for-all-relevance on quality at lower cost); review-theme
> feature support no longer depends on exact wording. See
> [docs/baselines/calibration_v0.8.md](docs/baselines/calibration_v0.8.md) and
> [docs/reviews/judgment_review_v0.8.md](docs/reviews/judgment_review_v0.8.md).
>
> In v0.7: keyword judgments see the seller's own product context
> (features, subtitle, description, category, brand), escalation is driven by
> deterministic risk signals instead of model confidence, and an
> evaluation-only mode asks the strong tier the same questions for
> comparison. Re-measured live ($0.1317 including the comparison; see
> [docs/baselines/live_v0.7.md](docs/baselines/live_v0.7.md)):
>
> | Agreement with fixtures (agreed / compared) | v0.6 live | v0.7 live | v0.7 strong tier |
> |---|---|---|---|
> | relevance (book / product) | 8/11, 10/12 | 8/11, 11/12 | 9/11, 12/12 |
> | intent (book / product) | 1/4, 3/5 | 3/4, 4/5 | 3/4, 4/5 |
> | entity (book / product) | 2/3, 6/6 | 3/3, 6/6 | not run |
> | equivalence (book / product) | 1/1, 2/2 | 1/1, 2/2 | not run |
>
> In v0.6: a **real, measured** baseline. Both example scenarios were run
> once through Vercel AI Gateway (Claude Haiku 4.5 fast tier, Claude Sonnet
> 5.5 strong tier) and recorded; CI replays the recordings offline. See
> [docs/baselines/live_v0.6.md](docs/baselines/live_v0.6.md).
>
> | Measured (live, 2026-10-04) | book | product |
> |---|---|---|
> | API calls (fast / strong) | 3 (2 / 1) | 5 (3 / 2) |
> | Input / output tokens | 6,755 / 2,392 | 11,602 / 3,049 |
> | Measured cost | $0.0225 | $0.0332 |
>
> Total $0.0557 against a planned $0.0515 expected / $0.1846 worst case. Live
> judgments agree with the fixture judgments on equivalence (100%) and on
> which keywords are entity-blocked (100%), less on relevance (73-83%) and
> intent (25-60%); rankings and recommendations shift. Details and the design
> implications are in
> [docs/architecture.md](docs/architecture.md#live-semantic-baseline-v06).
>
> From v0.5: the same semantic capability with far fewer calls and a
> bounded worst case. On the two example scenarios (synthetic recordings,
> estimates only; see [the benchmark](docs/benchmarks/semantic_cost_v0.5.md)):
>
> | | v0.4b | v0.5 |
> |---|---|---|
> | API calls (book / product) | 41 / 60 | 4 / 5 (planned 3 / 4, worst case 5 / 6) |
> | Expected cost (book / product) | $0.097 / $0.140 | $0.022 / $0.027 |
> | Worst-case cost (book / product) | $3.67 / $5.26 | $0.083 / $0.096 |
>
> How:
> * human decisions and deterministic rules (recipe entity lists, the
>   seller's own title words) answer requests before any model call, and
>   relevance/intent are skipped for families that cannot be ranked;
> * the cache stays per judgment; what is left is **batched** (relevance,
>   intent and entity together; equivalence in its own stage), matched by
>   stable item IDs, with each item validated and recorded on its own;
> * a cheap **fast tier** (Claude Haiku 4.5) answers; only uncertain,
>   failed or disputed items **escalate** to the strong tier (Claude Sonnet
>   5.5), with the reason recorded;
> * output budgets are derived from the response schema (no more 4,096
>   tokens per one-line answer), and cost guards use them;
> * `ResearchRun.plan_semantics()` shows every planned call with expected
>   and worst-case cost before anything runs.
>
> Also in place: recipes with rules sourced to official Amazon and KDP
> pages, normalization, coverage and decomposable scoring, backend packing,
> the listing audit, an append-only checksummed evidence store, keyword
> families, review themes, record/replay (CI stays offline), hard call and
> cost limits, human overrides and per-type evaluation.
>
> There are no live market-data providers, no CLI and no publishing yet.
> LLM calls happen only when explicitly enabled.

## Principles

1. **No opaque scores.** Every score is a defined formula over named inputs
   and can be broken down per keyword and per field. See
   [docs/architecture.md](docs/architecture.md#scoring).
2. **Deterministic where possible.** Limits, byte counting, deduplication,
   coverage, ranking math and compliance checks are plain code with tests.
3. **LLMs only for judgment and generation**, such as semantic relevance,
   review theme extraction, drafting copy and entity checks like "is this an
   author's name?". Their output always passes back through deterministic
   validation.
4. **Dated, sourced rules.** Amazon's rules change. Every limit and rule in a
   recipe cites a source with an `as_of` date and a status:
   * `verified`: confirmed against an official Amazon or KDP help page
     (the loader requires the URL);
   * `unverified`: not confirmable from official docs (the note explains
     why);
   * `heuristic`: an atlas convention, always a warning.

   See [docs/rule-sources.md](docs/rule-sources.md) for the current status
   of every rule. The last verification pass was 2026-10-03.
5. **Human approval before any write** to Amazon (SP-API listing updates, KDP
   changes).
6. **Independent of atlas-pathfinder.** Some architectural ideas are shared,
   but nothing is imported from it and there is no runtime dependency on it.

## Recipes

Recipes are TOML files in `src/atlas_amazon/recipes/data/`. Each one defines
fields, limits, audit rules, backend keyword budgets, scoring weights and
research priorities. A recipe can `extends` one parent:

```
amazon-base           (shared vocabulary and weights only; no limits or rules)
├── book              (KDP Help: title+subtitle < 200, description ≤ 4000, 7 keyword boxes)
└── physical-product  (Seller Central US: title ≤ 75, item highlights ≤ 125,
                       bullets, search terms < 250 bytes)
```

Current verified values at a glance (details and unverified items in
[docs/rule-sources.md](docs/rule-sources.md)):

| | Verified (official, 2026-10-03) | Still unverified |
|---|---|---|
| physical-product | title 75, item highlights 125, search terms 249 bytes, title, bullet and search-term content rules | bullet count (5) and length (500), description (2000), whether spaces count in bytes |
| book | title+subtitle 199, description 4000, 7 keywords, title and keyword content rules | 50-char keyword box |

## Quick start

Requires Python 3.11+. There are no runtime dependencies.

```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
```

(On Linux/macOS use `python3 -m venv .venv` and `.venv/bin/python`.)

```python
from atlas_amazon.audit import audit_listing
from atlas_amazon.backend import pack_backend_bytes
from atlas_amazon.models import Listing
from atlas_amazon.recipes import load_recipe

recipe = load_recipe("physical-product")
listing = Listing(
    {
        "title": "Acme Insulated Water Bottle, 32 oz",
        "bullets": ["Keeps drinks cold for 24 hours"],
        "search_terms": "flask gym hiking",
    }
)
report = audit_listing(listing, recipe)
for f in report.findings:
    print(f.severity.value, f.rule_id, f.message, f.source and f.source.as_of)

packed = pack_backend_bytes(
    ["hydro flask", "gym bottle", "camping"],
    max_bytes=recipe.fields["search_terms"].max_bytes,
    visible=[listing.text("title"), listing.text("bullets")],
    stopwords=recipe.backend.stopwords,
)
print(packed.text, packed.byte_count, [(e.term, e.reason.value) for e in packed.excluded])
```

### End-to-end research run (v0.3, offline)

```python
from atlas_amazon.report import render_markdown
from atlas_amazon.research import load_scenario

result = load_scenario("tests/fixtures/scenarios/book_cozy_mystery.json").run()
print(render_markdown(result))
```

To use your own inputs, build a `ResearchRun(product=..., listing=...,
recipe_id=..., run_id=..., providers=ResearchProviders(...), store=...,
started_at=...)` and call `.execute()`. See the example reports for a
[KDP book](docs/examples/book_cozy_mystery.md) and a
[physical product](docs/examples/physical_water_bottle.md).

### Evidence, scoring and proposals (v0.2 building blocks)

```python
from atlas_amazon.evidence import JsonlEvidenceStore
from atlas_amazon.keywords.scoring import (
    SignalValue,
    KeywordSignals,
    log_scaled_signal,
    score_keyword,
)
from atlas_amazon.planner import Proposal, validate_proposal
from atlas_amazon.providers import FixtureData, FixtureKeywordDataProvider

fixture = FixtureData.load("tests/fixtures/sample_us.json")
store = JsonlEvidenceStore("var/evidence.jsonl")  # append-only, checksummed
metrics = FixtureKeywordDataProvider(fixture).keyword_metrics(
    ["insulated water bottle"], marketplace="US", run_id="demo"
)
store.append_many(m for m in metrics if m.id not in store)
[metric] = metrics

signals = KeywordSignals(
    keyword="insulated water bottle",
    relevance=SignalValue(0.9),  # no evidence: shows up as a heuristic signal
    demand=log_scaled_signal(metric.payload["search_volume"], 120000, [metric.id]),
    competition=SignalValue(metric.payload["competition"], (metric.id,)),
    intent=SignalValue(0.7),
    competitor_coverage=SignalValue(0.5),
)
result = score_keyword(signals, recipe.keyword_weights)
for c in result.contributions:
    print(
        f"{c.signal:20} {c.weight:.2f} x {c.normalized_value:.3f} = {c.contribution:.3f}",
        c.evidence_ids,
    )
print("score", round(result.score, 3), "heuristic:", result.heuristic_signals)

proposal = Proposal.create(
    recipe=recipe,
    target_field="title",
    value="Acme Insulated Water Bottle, 32 oz",
    rationale="Adds 'insulated water bottle' (40k searches/month in fixture data).",
    evidence_ids=[metric.id],
    created_at=metric.retrieved_at,
)
check = validate_proposal(proposal, recipe=recipe, base=listing, evidence=store)
print("valid:", check.valid, [f.rule_id for f in check.blocking_findings])
```

### Live semantic judgments (opt-in)

Live calls are **off by default** and never happen in tests. To run one:

```bash
pip install -e ".[llm]"
```

Live calls go through **Vercel AI Gateway** by default (`default_live_transport()`,
Anthropic-compatible Messages API). The credential is `AI_GATEWAY_API_KEY` (or
`VERCEL_OIDC_TOKEN`) from the environment; it is handed to the SDK client and never
stored, logged or recorded. `ANTHROPIC_API_KEY` is not used (the direct
`AnthropicTransport` remains available with `DIRECT_FAST` / `DIRECT_STRONG` tiers).
Requests are pinned to Anthropic as the routed provider. Enable live calls with
`ATLAS_ALLOW_LIVE_LLM=1`, then:

```py
from atlas_amazon.evidence import InMemoryEvidenceStore
from atlas_amazon.research import ResearchRun, load_scenario
from atlas_amazon.semantic import (
    BatchedJudgmentProvider,
    LLMReviewThemeProvider,
    RecordingTransport,
    SemanticBudget,
    SemanticCache,
    UsageLedger,
    default_live_transport,
    render_plan_markdown,
)

ledger = UsageLedger(budget=SemanticBudget(max_live_calls=10, max_cost_usd=0.25))
cache = SemanticCache(".atlas/semantic-cache.jsonl")
live = RecordingTransport(default_live_transport(), ".atlas/book.recording.local.jsonl")
scenario = load_scenario("tests/fixtures/scenarios/book_cozy_mystery.json").with_providers(
    judgments=BatchedJudgmentProvider(live, ledger=ledger, cache=cache),
    review_themes=LLMReviewThemeProvider(live, ledger=ledger, cache=cache),
)
run = ResearchRun(
    product=scenario.product, listing=scenario.listing, recipe_id=scenario.product.recipe_id,
    run_id=scenario.run_id, providers=scenario.providers, store=InMemoryEvidenceStore(),
    started_at=scenario.started_at,
)
print(render_plan_markdown(run.plan_semantics()))  # inspect before spending anything
result = run.execute()
print(result.semantic_usage)
```

Model tiers, batch size and escalation are configurable:
`BatchedJudgmentProvider(live, tiers=ModelTiers(fast=..., strong=...),
batching=BatchSettings(max_items=40), escalation=EscalationPolicy(...))`.
`LLMJudgmentProvider` (one call per judgment) is still available.

Replay that recording later with `ReplayTransport(path)`; it makes no
network calls. Compare model and reference judgments per type with
`evaluate_judgments`. The committed recordings in
`tests/fixtures/recordings/` are **synthetic** (scripted). See
[docs/architecture.md](docs/architecture.md#live-semantic-providers-v04b)
for caching, prompt versioning, cost controls, human overrides and
evaluation, and
[Semantic cost and call efficiency](docs/architecture.md#semantic-cost-and-call-efficiency-v05)
for batching, tiers, escalation, budgets and plans.

## Layout

```
src/atlas_amazon/
  models.py  jsonvalue.py
  recipes/    TOML recipes, loader, schema
  keywords/   normalize, coverage, scoring
  backend/    hidden-keyword packing
  audit/      deterministic listing audit
  evidence/   identity, serialization, store Protocol, JSONL store
  providers/  Catalog/KeywordData/Suggestion/Review Protocols + fixture fakes
  planner/    Proposal + validate_proposal, backend plan, gap recommendations
  judgments/  JudgmentRequest, judgment Evidence contract, parse_judgment
  reviews/    review-theme Evidence, summaries, listing opportunities
  semantic/   LLM providers (batched + tiered, or one call each), escalation,
              output budgets, call plans, deterministic rules, prompts,
              cache, record/replay, usage limits, human overrides,
              evaluation, benchmark
  research/   ResearchRun orchestration, priority tasks, scenarios
  report/     report dict / JSON / Markdown (formatting only)
```

See [docs/architecture.md](docs/architecture.md) for the full architecture
and roadmap, and [docs/rule-sources.md](docs/rule-sources.md) for rule
provenance.
