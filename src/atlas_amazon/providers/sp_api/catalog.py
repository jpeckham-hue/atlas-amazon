"""SP-API Catalog Items (`searchCatalogItems`, v2022-04-01) as a read-only market-data source.

What it is used for, and what it is not:

* **Catalog and competitor evidence only.** For a keyword query it returns the
  catalog items Amazon's catalog search matches (titles, brands, bullet points,
  classifications, sales ranks); for ASINs it returns those items. Atlas uses
  them as competitor listings: candidate discovery from shared title/bullet
  phrases, and competitor-coverage shares.
* **Not demand.** The catalog search result order is not the shopper search
  ranking, and the API provides no search volume, conversion rate or ad
  competition. Those signals stay missing unless another source supplies them.

Evidence (all with provider `sp-api-catalog`, the run's marketplace, the
original response time as `retrieved_at`, and the request URL as
`source_url`, which carries no credentials):

* `catalog_item` per item, subject = ASIN, payload {asin, title, brand,
  bullets, classifications, sales_ranks, source, raw}: the same text fields as
  every other catalog provider, so domain code reads it unchanged; `raw` keeps
  the item exactly as returned.
* `catalog_search` per keyword query, subject = the query, payload {query,
  keywords, marketplace_id, included_data, page_size, result_asins (returned
  order), number_of_results, raw}.

Only the requested marketplace's data is used: an item with no summary for
that marketplace yields no evidence. An ASIN returned by several queries is
recorded once (first query wins). Responses that are not HTTP 200, are not a
JSON object with an `items` list, or fail in transport produce no evidence
and are listed in `failures`; nothing is invented.

**Call budget.** `max_calls_per_run` is a hard cap on live calls per run_id,
checked before each call; the source is free per call, so call volume is the
safety budget. `plan()` shows the calls before any are made.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from atlas_amazon.evidence.identity import make_evidence
from atlas_amazon.jsonvalue import thaw
from atlas_amazon.keywords.normalize import normalize_text, tokenize
from atlas_amazon.models import Evidence, EvidenceKind, is_valid_asin
from atlas_amazon.providers.sp_api.http import (
    HttpReplayMiss,
    HttpRequest,
    HttpResponse,
    HttpTransport,
    HttpTransportError,
    LiveMarketDisabled,
)

PROVIDER = "sp-api-catalog"
CATALOG_PATH = "/catalog/2022-04-01/items"
INCLUDED_DATA = "summaries,attributes,classifications,salesRanks"
RATE_LIMIT_PER_SECOND = 5.0  # documented searchCatalogItems usage plan (burst 5)
MAX_PAGE_SIZE = 20
MAX_IDENTIFIERS = 20
NA = "https://sellingpartnerapi-na.amazon.com"
EU = "https://sellingpartnerapi-eu.amazon.com"
# Atlas marketplace code -> (SP-API marketplace ID, regional endpoint).
MARKETPLACES: Mapping[str, tuple[str, str]] = {
    "US": ("ATVPDKIKX0DER", NA),
    "CA": ("A2EUQ1WTGCTBG2", NA),
    "UK": ("A1F83G8C2ARO7P", EU),
    "DE": ("A1PA6795UKMFR9", EU),
}


class UnsupportedMarketplace(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MarketCallPlan:
    provider: str
    operation: str
    marketplace: str
    queries: tuple[str, ...]
    identifiers: tuple[str, ...]
    calls: int
    rate_limit_per_second: float
    call_cap: int
    cost_per_call_usd: float = 0.0
    notes: tuple[str, ...] = ()

    @property
    def within_cap(self) -> bool:
        return self.calls <= self.call_cap

    @property
    def expected_cost_usd(self) -> float:
        return self.calls * self.cost_per_call_usd

    @property
    def worst_case_cost_usd(self) -> float:
        return self.call_cap * self.cost_per_call_usd


def render_market_plan(plan: MarketCallPlan) -> str:
    lines = [
        f"{plan.provider} {plan.operation} ({plan.marketplace}): {plan.calls} network calls "
        f"(cap {plan.call_cap}, {'within' if plan.within_cap else 'OVER'} cap); rate limit "
        f"{plan.rate_limit_per_second:g} req/s; cost ${plan.expected_cost_usd:.2f} expected, "
        f"${plan.worst_case_cost_usd:.2f} worst case (no per-call fee)",
    ]
    lines += [f"  query: {q!r}" for q in plan.queries]
    if plan.identifiers:
        lines.append(f"  ASINs: {', '.join(plan.identifiers)}")
    lines += [f"  note: {n}" for n in plan.notes]
    return "\n".join(lines)


def _marketplace(marketplace: str) -> tuple[str, str]:
    try:
        return MARKETPLACES[marketplace]
    except KeyError:
        raise UnsupportedMarketplace(f"no SP-API marketplace mapping for {marketplace!r}") from None


def _bullets(attributes: Mapping[str, Any], marketplace_id: str) -> tuple[str, ...]:
    out: list[str] = []
    for entry in attributes.get("bullet_point", ()) or ():
        if not isinstance(entry, Mapping) or not isinstance(entry.get("value"), str):
            continue
        if entry.get("marketplace_id") not in (None, marketplace_id):
            continue
        if entry["value"].strip() and entry["value"] not in out:
            out.append(entry["value"].strip())
    return tuple(out)


def item_payload(item: Mapping[str, Any], marketplace_id: str) -> dict[str, Any] | None:
    """The `catalog_item` payload for one SP-API item, or None if unusable here."""
    asin = item.get("asin")
    if not isinstance(asin, str) or not is_valid_asin(asin):
        return None
    summaries = [
        s
        for s in item.get("summaries", ()) or ()
        if isinstance(s, Mapping) and s.get("marketplaceId") == marketplace_id
    ]
    if not summaries or not isinstance(summaries[0].get("itemName"), str):
        return None  # no data for this marketplace: not our evidence
    summary = summaries[0]
    attributes = item.get("attributes") if isinstance(item.get("attributes"), Mapping) else {}
    classifications = [
        c.get("displayName")
        for group in item.get("classifications", ()) or ()
        if isinstance(group, Mapping) and group.get("marketplaceId") == marketplace_id
        for c in group.get("classifications", ()) or ()
        if isinstance(c, Mapping) and isinstance(c.get("displayName"), str)
    ]
    sales_ranks = [
        group
        for group in item.get("salesRanks", ()) or ()
        if isinstance(group, Mapping) and group.get("marketplaceId") == marketplace_id
    ]
    payload: dict[str, Any] = {
        "asin": asin,
        "title": summary["itemName"],
        "bullets": list(_bullets(attributes, marketplace_id)),
        "classifications": classifications,
        "sales_ranks": thaw(sales_ranks),
        "source": "sp-api:searchCatalogItems",
        "raw": thaw(item),
    }
    brand = summary.get("brand") or summary.get("brandName")
    if isinstance(brand, str) and brand.strip():
        payload["brand"] = brand.strip()
    return payload


@dataclass
class SpApiCatalogProvider:
    """Read-only catalog provider over SP-API `searchCatalogItems`."""

    transport: HttpTransport
    max_calls_per_run: int = 10
    page_size: int = 10
    query_limit: int | None = None  # first N keyword queries only; the rest are listed as skipped
    name: str = PROVIDER
    failures: list[tuple[str, str]] = field(default_factory=list)  # (query or ASINs, reason)
    halts: list[str] = field(default_factory=list)
    _calls: dict[str | None, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 1 <= self.page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be within 1..{MAX_PAGE_SIZE}")
        if self.max_calls_per_run < 0:
            raise ValueError("max_calls_per_run must be >= 0")

    # -- planning -------------------------------------------------------------

    @property
    def is_live(self) -> bool:
        return self.transport.is_live

    def _queries(self, keywords: Sequence[str]) -> list[str]:
        queries = [q for q in dict.fromkeys(normalize_text(k) for k in keywords) if q]
        return queries if self.query_limit is None else queries[: self.query_limit]

    def plan(
        self, *, marketplace: str, keywords: Sequence[str] = (), asins: Sequence[str] = ()
    ) -> MarketCallPlan:
        _marketplace(marketplace)
        queries = self._queries(keywords)
        ids = list(dict.fromkeys(asins))
        calls = len(queries) + math.ceil(len(ids) / MAX_IDENTIFIERS)
        return MarketCallPlan(
            provider=self.name,
            operation="searchCatalogItems",
            marketplace=marketplace,
            queries=tuple(queries),
            identifiers=tuple(ids),
            calls=calls,
            rate_limit_per_second=RATE_LIMIT_PER_SECOND,
            call_cap=self.max_calls_per_run,
            notes=(
                f"one call per keyword query (pageSize {self.page_size}, first page only); "
                f"ASIN lookups in groups of {MAX_IDENTIFIERS}",
                "catalog evidence only: no search volume, conversion or ad competition",
            ),
        )

    # -- calls ------------------------------------------------------------------

    def calls_made(self, run_id: str | None) -> int:
        return self._calls.get(run_id, 0)

    def _request(self, marketplace: str, params: Mapping[str, str]) -> HttpRequest:
        marketplace_id, base = _marketplace(marketplace)
        return HttpRequest.get(
            base,
            CATALOG_PATH,
            {"marketplaceIds": marketplace_id, "includedData": INCLUDED_DATA, **params},
        )

    def _call(self, label: str, request: HttpRequest, run_id: str | None) -> HttpResponse | None:
        if self.transport.is_live:
            if self.calls_made(run_id) >= self.max_calls_per_run:
                reason = f"max_calls_per_run={self.max_calls_per_run} reached"
                self.halts.append(reason)
                self.failures.append((label, "call_limit"))
                return None
            self._calls[run_id] = self.calls_made(run_id) + 1
        try:
            response = self.transport.send(request)
        except LiveMarketDisabled:
            raise
        except HttpReplayMiss:
            self.failures.append((label, "replay_miss"))
            return None
        except (HttpTransportError, OSError) as exc:
            self.failures.append((label, f"transport_error: {type(exc).__name__}"))
            return None
        if response.status != 200:
            code = ""
            if isinstance(response.body, Mapping) and isinstance(response.body.get("errors"), list):
                first = response.body["errors"][0] if response.body["errors"] else {}
                code = f" {first.get('code', '')}" if isinstance(first, Mapping) else ""
            self.failures.append((label, f"http_{response.status}{code}"))
            return None
        if not isinstance(response.body, Mapping) or not isinstance(
            response.body.get("items"), list
        ):
            self.failures.append((label, "malformed: expected an object with an items list"))
            return None
        return response

    def _items(
        self,
        response: HttpResponse,
        request: HttpRequest,
        *,
        marketplace: str,
        run_id: str | None,
        seen: set[str],
        label: str,
    ) -> tuple[list[Evidence], list[str]]:
        marketplace_id, _ = _marketplace(marketplace)
        out, asins = [], []
        for item in response.body["items"]:
            payload = item_payload(item, marketplace_id) if isinstance(item, Mapping) else None
            if payload is None:
                self.failures.append((label, "item skipped: unusable for this marketplace"))
                continue
            asins.append(payload["asin"])
            if payload["asin"] in seen:
                continue  # already recorded from an earlier query in this call set
            seen.add(payload["asin"])
            out.append(
                make_evidence(
                    provider=self.name,
                    kind=EvidenceKind.CATALOG_ITEM,
                    marketplace=marketplace,
                    retrieved_at=datetime.fromisoformat(response.retrieved_at),
                    payload=payload,
                    subject=payload["asin"],
                    run_id=run_id,
                    source_url=request.url,
                )
            )
        return out, list(dict.fromkeys(asins))

    def search(
        self, keywords: Sequence[str], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]:
        """Catalog items for each keyword query, plus one `catalog_search` record per query."""
        marketplace_id, _ = _marketplace(marketplace)
        out: list[Evidence] = []
        seen: set[str] = set()
        queries = self._queries(keywords)
        for query in [q for q in dict.fromkeys(normalize_text(k) for k in keywords) if q]:
            if query not in queries:
                self.failures.append((query, f"skipped: query_limit={self.query_limit}"))
        for query in queries:
            words = [t for t in tokenize(query)]
            request = self._request(
                marketplace, {"keywords": ",".join(words), "pageSize": str(self.page_size)}
            )
            response = self._call(query, request, run_id)
            if response is None:
                continue
            items, asins = self._items(
                response, request, marketplace=marketplace, run_id=run_id, seen=seen, label=query
            )
            out.append(
                make_evidence(
                    provider=self.name,
                    kind=EvidenceKind.CATALOG_SEARCH,
                    marketplace=marketplace,
                    retrieved_at=datetime.fromisoformat(response.retrieved_at),
                    payload={
                        "query": query,
                        "keywords": words,
                        "marketplace_id": marketplace_id,
                        "included_data": INCLUDED_DATA,
                        "page_size": self.page_size,
                        "result_asins": asins,
                        "number_of_results": response.body.get("numberOfResults"),
                        "raw": thaw(response.body),
                    },
                    subject=query,
                    run_id=run_id,
                    source_url=request.url,
                )
            )
            out += items
        return out

    def get_items(
        self, asins: Sequence[str], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]:
        """`CatalogProvider`: catalog items for ASINs (identifier search, 20 per call)."""
        ids = list(dict.fromkeys(asins))
        for asin in ids:
            if not is_valid_asin(asin):
                raise ValueError(f"invalid ASIN: {asin!r}")
        out: list[Evidence] = []
        seen: set[str] = set()
        for start in range(0, len(ids), MAX_IDENTIFIERS):
            group = ids[start : start + MAX_IDENTIFIERS]
            label = ",".join(group)
            request = self._request(marketplace, {"identifiers": label, "identifiersType": "ASIN"})
            response = self._call(label, request, run_id)
            if response is None:
                continue
            items, _ = self._items(
                response, request, marketplace=marketplace, run_id=run_id, seen=seen, label=label
            )
            out += items
        return out
