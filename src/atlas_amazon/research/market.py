"""Compare a research run with live market (catalog) evidence against its fixture-only run.

Three things are kept apart throughout:

* **market opportunity**: what the catalog evidence shows sellers use (phrases
  shared by discovered competitor listings);
* **product relevance**: what the semantic judgments say about the keyword
  for this product (unchanged here; new candidates without judgments stay
  unjudged);
* **product truth**: what the seller's own information supports. A keyword the
  market makes tempting but the product does not support stays blocked from
  recommendations and backend terms (`unsupported_by_product`).

Catalog evidence is not demand: a new candidate with no keyword metric stays
unscored on demand, and nothing here estimates search volume.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas_amazon.keywords.candidates import competitor_listing
from atlas_amazon.keywords.normalize import normalize_text
from atlas_amazon.models import Evidence, EvidenceKind
from atlas_amazon.research.run import ResearchResult


@dataclass(frozen=True, slots=True)
class KeywordPresence:
    keyword: str
    market_items: int  # market catalog items whose text contains the phrase
    items_seen: int


@dataclass(frozen=True, slots=True)
class RankChange:
    keyword: str
    before: int | None  # 1-based rank, None when not ranked
    after: int | None


@dataclass(frozen=True, slots=True)
class TemptingKeyword:
    keyword: str
    unsupported_terms: tuple[str, ...]
    market_items: int  # market catalog items containing the phrase
    recommended: bool  # must stay False
    packed: bool  # must stay False


@dataclass(frozen=True, slots=True)
class MarketComparison:
    provider: str
    queries: tuple[str, ...]
    market_items: tuple[str, ...]  # ASINs discovered by the market provider
    new_candidates: tuple[str, ...]
    confirmed: tuple[KeywordPresence, ...]  # fixture candidates found in market listings
    absent: tuple[str, ...]  # fixture candidates found in no market listing
    rank_changes: tuple[RankChange, ...]
    recommendations_added: tuple[str, ...]
    recommendations_removed: tuple[str, ...]
    tempting_unsupported: tuple[TemptingKeyword, ...]
    new_without_demand: tuple[str, ...]  # new candidates with no keyword metric (stay missing)


def _market_evidence(result: ResearchResult, store, provider: str) -> list[Evidence]:
    ids = dict.fromkeys(i for ids in result.evidence.ids_by_kind.values() for i in ids)
    return [e for e in (store.get(i) for i in ids) if e.provider == provider]


def _contains(evidence: Evidence, phrase: str) -> bool:
    listing = competitor_listing(evidence)
    text = " ".join(" ".join(listing.segments(name)) for name in listing.fields)
    return f" {phrase} " in f" {normalize_text(text)} "


def compare_market(
    baseline: ResearchResult, market: ResearchResult, store, *, provider: str
) -> MarketComparison:
    """`store` holds the market run's evidence; `provider` names the market provider."""
    evidence = _market_evidence(market, store, provider)
    items = [e for e in evidence if e.kind == EvidenceKind.CATALOG_ITEM]
    searches = [e for e in evidence if e.kind == EvidenceKind.CATALOG_SEARCH]

    def presence(keyword: str) -> int:
        return sum(_contains(e, keyword) for e in items)

    before = {c.keyword for c in baseline.candidates}
    after = [c.keyword for c in market.candidates]
    confirmed, absent = [], []
    for keyword in sorted(before):
        n = presence(keyword)
        if n:
            confirmed.append(KeywordPresence(keyword, n, len(items)))
        else:
            absent.append(keyword)
    rank_before = {s.keyword: i for i, s in enumerate(baseline.ranked, 1)}
    rank_after = {s.keyword: i for i, s in enumerate(market.ranked, 1)}
    changes = [
        RankChange(k, rank_before.get(k), rank_after.get(k))
        for k in sorted(
            set(rank_before) | set(rank_after), key=lambda k: (rank_after.get(k, 999), k)
        )
        if rank_before.get(k) != rank_after.get(k)
    ]
    recs_before = [r.keyword for r in baseline.recommendations]
    recs_after = [r.keyword for r in market.recommendations]
    packed = set(market.backend_plan.packed_keywords) if market.backend_plan else set()
    tempting = tuple(
        TemptingKeyword(
            u.keyword,
            u.unsupported_terms,
            presence(u.keyword),
            u.keyword in recs_after,
            u.keyword in packed,
        )
        for u in market.unsupported_opportunities
    )
    new = tuple(k for k in after if k not in before)
    metric_keywords = {
        normalize_text(str(store.get(i).payload.get("keyword", "")))
        for i in market.evidence.ids_by_kind.get(EvidenceKind.KEYWORD_METRIC.value, ())
    }
    return MarketComparison(
        provider=provider,
        queries=tuple(str(e.payload["query"]) for e in searches),
        market_items=tuple(e.subject or "" for e in items),
        new_candidates=new,
        confirmed=tuple(confirmed),
        absent=tuple(absent),
        rank_changes=tuple(changes),
        recommendations_added=tuple(k for k in recs_after if k not in recs_before),
        recommendations_removed=tuple(k for k in recs_before if k not in recs_after),
        tempting_unsupported=tempting,
        new_without_demand=tuple(k for k in new if k not in metric_keywords),
    )


def render_market_comparison(name: str, c: MarketComparison) -> list[str]:
    def listed(values) -> str:
        return ", ".join(f"`{v}`" for v in values) if values else "none"

    out = [
        f"### {name}",
        "",
        f"- Market queries ({c.provider}): {listed(c.queries)}; "
        f"{len(c.market_items)} catalog items kept as competitor listings.",
        f"- New candidate keywords: {listed(c.new_candidates)}.",
        f"- New candidates with no demand data (stay unscored on demand): "
        f"{listed(c.new_without_demand)}.",
        "- Fixture candidates confirmed by market listings: "
        + (
            ", ".join(f"`{p.keyword}` ({p.market_items}/{p.items_seen})" for p in c.confirmed)
            or "none"
        )
        + ".",
        f"- Fixture candidates absent from market listings: {listed(c.absent)}.",
        f"- Recommendations added: {listed(c.recommendations_added)}; removed: "
        f"{listed(c.recommendations_removed)}.",
        "",
    ]
    if c.rank_changes:
        out += ["| Keyword | Rank before | Rank after |", "|---|---|---|"]
        out += [f"| {r.keyword} | {r.before or '-'} | {r.after or '-'} |" for r in c.rank_changes]
        out.append("")
    else:
        out += ["Ranking unchanged.", ""]
    if c.tempting_unsupported:
        out += [
            "| Unsupported keyword | Unsupported terms | Market listings | Recommended | Packed |",
            "|---|---|---|---|---|",
        ]
        out += [
            f"| {t.keyword} | {', '.join(t.unsupported_terms)} | {t.market_items} | "
            f"{'yes' if t.recommended else 'no'} | {'yes' if t.packed else 'no'} |"
            for t in c.tempting_unsupported
        ]
        out.append("")
    return out


def render_market_report(
    title: str, header: list[str], comparisons: dict[str, MarketComparison]
) -> str:
    """A markdown report of market comparisons, one section per scenario."""
    out = [f"# {title}", "", *header, ""]
    for name, comparison in comparisons.items():
        out += render_market_comparison(name, comparison)
    return "\n".join(out).rstrip() + "\n"
