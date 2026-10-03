# atlas-amazon

An evidence-backed Amazon SEO and listing optimization engine. It supports
books (KDP) first, then general Amazon products through category/product
**recipes**.

Every recommendation should be explainable. The engine records where a fact
came from, which marketplace it applies to and when it was observed. It
records which dated rule a check enforces, and how each score breaks down
into its parts.

> Status: **v0.2: offline foundation.** In place:
> * recipe loading, with rules sourced to official Amazon and KDP pages;
> * keyword normalization, coverage and decomposable scoring;
> * backend keyword packing and the listing audit;
> * an append-only, checksummed evidence store;
> * provider Protocols with fixture-backed fakes;
> * evidence-linked proposals that are only valid after passing the audit.
>
> Everything is deterministic and offline. There are no live providers, no
> LLM calls, no CLI and no publishing yet.

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

### Evidence, scoring and proposals (v0.2, offline)

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
  planner/    Proposal + validate_proposal
```

See [docs/architecture.md](docs/architecture.md) for the full architecture
and roadmap, and [docs/rule-sources.md](docs/rule-sources.md) for rule
provenance.
