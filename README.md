# atlas-amazon

An evidence-backed Amazon SEO and listing optimization engine. It supports
books (KDP) first, then general Amazon products through category/product
**recipes**.

Every recommendation should be explainable. The engine records where a fact
came from, which marketplace it applies to and when it was observed. It
records which dated rule a check enforces, and how each score breaks down
into its parts.

> Status: **v0.1 scaffold.** The local domain core is in place: models, recipe
> loading, keyword normalization and coverage, backend keyword packing, and
> listing audit primitives. There are no live provider integrations, no LLM
> calls and no publishing yet.

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
   recipe cites a source with an `as_of` date and a status (`verified`,
   `unverified` or `heuristic`). Nothing in v0.1 is marked `verified` yet.
5. **Human approval before any write** to Amazon (SP-API listing updates, KDP
   changes).
6. **Independent of atlas-pathfinder.** Some architectural ideas are shared,
   but nothing is imported from it and there is no runtime dependency on it.

## Recipes

Recipes are TOML files in `src/atlas_amazon/recipes/data/`. Each one defines
fields, limits, audit rules, backend keyword budgets, scoring weights and
research priorities. A recipe can `extends` one parent:

```
amazon-base
├── book              (KDP: title+subtitle, 4000-char description, 7×50 keyword slots)
└── physical-product  (Seller Central: bullets, 250-byte search terms)
```

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

## Layout

See [docs/architecture.md](docs/architecture.md) for the full architecture,
the planned file tree and the roadmap.
