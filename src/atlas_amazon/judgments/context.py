"""First-party product context for keyword judgments (v0.7).

v0.6 judgments saw only the product title and seed keywords, so a model
correctly marked keywords about real features ("leak proof", "double wall
vacuum") as unsupported. `product_context` adds what the seller supplied
about their own product, and nothing else:

* `product_title`, `seeds` (as before);
* `category`: the recipe id ("book", "physical-product");
* `subtitle`: the listing subtitle, for recipes that have one (books);
* `brand` / `author`: from product attributes, or the listing's brand field;
* `features`: product attributes `features`, else the listing's bullets
  (both are the seller's own statements; at most `MAX_FEATURES`);
* `description`: the listing description, at most `MAX_DESCRIPTION_CHARS`
  (cut at a word boundary, with `description_truncated: true`, never silently).

Competitor catalog data, reviews and review themes are never included: they
are not facts about this product. Empty fields are omitted, so a product
with no extra metadata gets the v0.6 context plus `category`. The context is part of
each request's input, so its hash (and every cache key) changes whenever the
context does.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from atlas_amazon.models import Listing, ProductInput
from atlas_amazon.recipes.schema import Recipe

MAX_FEATURES = 10
MAX_DESCRIPTION_CHARS = 500


def _clean(values: Sequence[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip() and value.strip() not in out:
            out.append(value.strip())
    return out


def product_context(
    product: ProductInput, listing: Listing, recipe: Recipe, seeds: Sequence[str]
) -> dict[str, Any]:
    attrs = product.attributes
    context: dict[str, Any] = {
        "product_title": product.title,
        "seeds": list(seeds),
        "category": recipe.id,
    }
    if "subtitle" in recipe.fields and listing.text("subtitle").strip():
        context["subtitle"] = listing.text("subtitle").strip()
    brand = attrs.get("brand") or listing.text("brand")
    if isinstance(brand, str) and brand.strip():
        context["brand"] = brand.strip()
    author = attrs.get("author")
    if isinstance(author, str) and author.strip():
        context["author"] = author.strip()
    raw = attrs.get("features")
    features = _clean(raw) if isinstance(raw, list | tuple) else []
    if not features:
        features = _clean(listing.segments("bullets"))
    if features:
        context["features"] = features[:MAX_FEATURES]
    description = listing.text("description").strip()
    if description:
        if len(description) > MAX_DESCRIPTION_CHARS:
            cut = description[:MAX_DESCRIPTION_CHARS].rsplit(" ", 1)[0]
            context["description"] = cut
            context["description_truncated"] = True
        else:
            context["description"] = description
    return context


def first_party_text(context: dict[str, Any] | Any) -> list[str]:
    """Every first-party text in a judgment context, for deterministic checks."""
    texts = [str(context.get("product_title", ""))]
    for key in ("subtitle", "brand", "author", "description"):
        if context.get(key):
            texts.append(str(context[key]))
    texts += [str(s) for s in context.get("seeds", ())]
    texts += [str(f) for f in context.get("features", ())]
    return [t for t in texts if t.strip()]
