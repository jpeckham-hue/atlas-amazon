"""Render a ResearchResult as a JSON-ready dict or Markdown.

This layer formats, it does not decide. It computes no scores, thresholds,
rankings or recommendations; it only copies and lays out what the domain
produced. Every derived figure in the output keeps its evidence IDs.
"""

from __future__ import annotations

import json
from typing import Any

from atlas_amazon.jsonvalue import thaw
from atlas_amazon.models import Finding
from atlas_amazon.research.run import ResearchResult


def _finding(f: Finding) -> dict[str, Any]:
    return {
        "rule_id": f.rule_id,
        "severity": f.severity.value,
        "field": f.field,
        "message": f.message,
        "observed": thaw(f.observed) if f.observed is not None else None,
        "limit": f.limit,
        "source": (
            {
                "id": f.source.id,
                "status": f.source.status.value,
                "url": f.source.url,
                "as_of": f.source.as_of.isoformat(),
            }
            if f.source
            else None
        ),
    }


def report_dict(result: ResearchResult) -> dict[str, Any]:
    m = result.metadata
    ev = result.evidence
    plan = result.backend_plan
    return {
        "run": {
            "run_id": m.run_id,
            "started_at": m.started_at.isoformat(),
            "atlas_version": m.atlas_version,
            "recipe": {
                "id": m.recipe_id,
                "version": m.recipe_version,
                "lineage": list(m.recipe_lineage),
            },
            "research_priorities": list(m.research_priorities),
            "marketplace": m.marketplace,
            "product": {
                "title": m.product_title,
                "asin": m.asin,
                "competitor_asins": list(m.competitor_asins),
            },
            "seeds": {"values": list(m.seeds), "source": m.seeds_source},
            "providers": dict(m.providers),
            "config": {
                "top_n": m.config.top_n,
                "min_competitor_support": m.config.min_competitor_support,
                "review_limit": m.config.review_limit,
            },
            "evidence_fingerprint": m.evidence_fingerprint,
        },
        "tasks": [
            {
                "priority": t.priority,
                "task": t.task,
                "status": t.status.value,
                "providers": list(t.providers),
                "evidence_ids": list(t.evidence_ids),
                "new_records": t.new_records,
                "reused_records": t.reused_records,
                "note": t.note,
            }
            for t in result.tasks
        ],
        "evidence": {
            "total": ev.total,
            "by_kind": dict(ev.by_kind),
            "by_provider": dict(ev.by_provider),
            "ids_by_kind": {k: list(v) for k, v in ev.ids_by_kind.items()},
            "missing": {
                "competitors_without_catalog": list(ev.competitors_without_catalog),
                "seeds_without_suggestions": list(ev.seeds_without_suggestions),
                "candidates_without_metrics": list(ev.candidates_without_metrics),
                "asins_without_reviews": list(ev.asins_without_reviews),
            },
        },
        "audit": {
            "passed": result.audit.passed,
            "findings": [_finding(f) for f in result.audit.findings],
        },
        "candidates": [
            {
                "keyword": c.keyword,
                "sources": [s.value for s in c.sources],
                "evidence_ids": list(c.evidence_ids),
            }
            for c in result.candidates
        ],
        "ranked_keywords": [
            {
                "rank": rank,
                "keyword": s.keyword,
                "score": s.score,
                "heuristic_signals": list(s.heuristic_signals),
                "evidence_ids": list(s.evidence_ids),
                "signals": [
                    {
                        "signal": c.signal,
                        "raw": c.raw_value,
                        "normalized": c.normalized_value,
                        "inverted": c.inverted,
                        "weight": c.weight,
                        "contribution": c.contribution,
                        "heuristic": c.heuristic,
                        "evidence_ids": list(c.evidence_ids),
                        "derivation": result.derivation(s.keyword).notes[c.signal],
                    }
                    for c in s.contributions
                ],
            }
            for rank, s in enumerate(result.ranked, 1)
        ],
        "unscored_keywords": [
            {
                "keyword": d.keyword,
                "missing_signals": list(d.missing),
                "notes": {k: d.notes[k] for k in d.missing},
                "evidence_ids": list(d.candidate.evidence_ids),
            }
            for d in result.unscored
        ],
        "coverage": None
        if result.coverage is None
        else {
            "exact_rate": result.coverage.exact_rate,
            "token_rate": result.coverage.token_rate,
            "placement_score": result.coverage.placement_score,
            "field_weights": dict(result.coverage.field_weights),
            "keywords": [
                {
                    "keyword": k.keyword,
                    "exact_fields": list(k.exact_fields),
                    "best_field": k.best_field,
                    "placement": k.placement_score,
                    "token_fraction": k.token_fraction,
                }
                for k in result.coverage.keywords
            ],
        },
        "backend_plan": None
        if plan is None
        else {
            "field": plan.field_name,
            "mode": plan.mode,
            "used": plan.used,
            "capacity": plan.capacity,
            "packed_keywords": list(plan.packed_keywords),
            "retained_current": list(plan.retained),
            "proposal_id": plan.proposal.id if plan.proposal else None,
            "note": plan.note,
            "exclusions": [
                {"term": e.term, "reason": e.reason.value, "candidate": e.candidate}
                for e in plan.exclusions
            ],
            "rule_exclusions": [
                {"keyword": r.keyword, "rule_id": r.rule_id, "terms": list(r.terms)}
                for r in plan.rule_exclusions
            ],
        },
        "recommendations": [
            {
                "kind": r.kind.value,
                "keyword": r.keyword,
                "rank": r.rank,
                "score": r.score,
                "current_fields": list(r.current_fields),
                "suggested_fields": list(r.suggested_fields),
                "blocked_fields": [{"field": f, "rule_id": rule} for f, rule in r.blocked_fields],
                "reason": r.reason,
                "evidence_ids": list(r.evidence_ids),
                "heuristic_signals": list(r.heuristic_signals),
                "covered_by_proposal": r.covered_by_proposal,
            }
            for r in result.recommendations
        ],
        "proposals": [
            {
                "id": p.id,
                "target_field": p.target_field,
                "value": p.value if isinstance(p.value, str) else list(p.value),
                "rationale": p.rationale,
                "basis": p.basis.value,
                "evidence_ids": list(p.evidence_ids),
                "recipe": {"id": p.recipe_id, "version": p.recipe_version},
                "created_at": p.created_at.isoformat(),
                "validation": {
                    "valid": v.valid,
                    "problems": list(v.problems),
                    "missing_evidence": list(v.missing_evidence),
                    "blocking_findings": [_finding(f) for f in v.blocking_findings],
                    "warnings": [
                        _finding(f)
                        for f in (v.audit.warnings if v.audit else ())
                        if f.field == p.target_field
                    ],
                },
            }
            for p, v in zip(result.proposals, result.validations, strict=True)
        ],
    }


def report_json(result: ResearchResult) -> str:
    return json.dumps(report_dict(result), indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _ids(ids: Any, limit: int = 4) -> str:
    ids = list(ids)
    if not ids:
        return "none"
    shown = ", ".join(f"`{i}`" for i in ids[:limit])
    return shown + (f" (+{len(ids) - limit} more)" if len(ids) > limit else "")


def render_markdown(result: ResearchResult) -> str:
    d = report_dict(result)
    run, ev = d["run"], d["evidence"]
    out: list[str] = []
    w = out.append

    w(f"# Research report: {run['product']['title']}")
    w("")
    w(f"- Run: `{run['run_id']}` at {run['started_at']} (atlas {run['atlas_version']})")
    w(
        f"- Recipe: `{run['recipe']['id']}` {run['recipe']['version']} "
        f"({' > '.join(run['recipe']['lineage'])}), marketplace {run['marketplace']}"
    )
    w(f"- Seeds ({run['seeds']['source']}): {', '.join(run['seeds']['values'])}")
    w("- Providers: " + ", ".join(f"{k}={v or 'none'}" for k, v in run["providers"].items()))
    w(f"- Evidence fingerprint: `{run['evidence_fingerprint'][:16]}`")
    w("")

    w("## Research tasks")
    w("")
    w("| Priority | Task | Status | New / reused | Note |")
    w("|---|---|---|---|---|")
    for t in d["tasks"]:
        w(
            f"| {t['priority']} | {t['task'] or '-'} | {t['status']} | "
            f"{t['new_records']} / {t['reused_records']} | {t['note']} |"
        )
    w("")

    w("## Evidence summary")
    w("")
    w(
        f"{ev['total']} records. By kind: "
        + (", ".join(f"{k} {n}" for k, n in ev["by_kind"].items()) or "none")
        + "."
    )
    w("")
    for label, values in ev["missing"].items():
        if values:
            w(f"- Missing, {label.replace('_', ' ')}: {', '.join(values)}")
    w("")

    w(f"## Current listing audit: {'passed' if d['audit']['passed'] else 'FAILED'}")
    w("")
    if not d["audit"]["findings"]:
        w("No findings.")
    for f in d["audit"]["findings"]:
        src = f["source"]
        provenance = f" [{src['id']}, {src['status']}]" if src else ""
        w(f"- **{f['severity']}** `{f['rule_id']}`: {f['message']}{provenance}")
    w("")

    w("## Ranked keywords")
    w("")
    if not d["ranked_keywords"]:
        w("No keyword had evidence for every required signal.")
    else:
        w(
            "| # | Keyword | Score | Relevance* | Demand | Competition (inv.) | Intent* | "
            "Competitor coverage |"
        )
        w("|---|---|---|---|---|---|---|---|")
        for k in d["ranked_keywords"]:
            cells = {s["signal"]: f"{s['contribution']:.3f}" for s in k["signals"]}
            w(
                f"| {k['rank']} | {k['keyword']} | {k['score']:.3f} | {cells['relevance']} | "
                f"{cells['demand']} | {cells['competition']} | {cells['intent']} | "
                f"{cells['competitor_coverage']} |"
            )
        w("")
        w("Cells show weighted contributions. *Heuristic placeholder (no evidence).")
    w("")

    w("## Signal breakdown")
    w("")
    for k in d["ranked_keywords"]:
        w(f"### {k['rank']}. {k['keyword']}: {k['score']:.3f}")
        w("")
        w("| Signal | Raw | Normalized | Weight | Contribution | Evidence | Derivation |")
        w("|---|---|---|---|---|---|---|")
        for s in k["signals"]:
            w(
                f"| {s['signal']}{' (heuristic)' if s['heuristic'] else ''} | {s['raw']:.3f} | "
                f"{s['normalized']:.3f} | {s['weight']:.2f} | {s['contribution']:.3f} | "
                f"{_ids(s['evidence_ids'], 2)} | {s['derivation']} |"
            )
        w("")

    if d["unscored_keywords"]:
        w("## Unscored keywords (missing evidence)")
        w("")
        for u in d["unscored_keywords"]:
            reasons = "; ".join(f"{k}: {v}" for k, v in u["notes"].items())
            w(f"- {u['keyword']}: {reasons}")
        w("")

    w("## Recommendations")
    w("")
    if not d["recommendations"]:
        w("None." if d["ranked_keywords"] else "None (no ranked keywords).")
    for r in d["recommendations"]:
        packed = (
            f" Packed by proposal `{r['covered_by_proposal']}`." if r["covered_by_proposal"] else ""
        )
        consider = ", ".join(r["suggested_fields"]) or "no field (all blocked by recipe rules)"
        blocked = "".join(f" Not {b['field']} (`{b['rule_id']}`)." for b in r["blocked_fields"])
        w(
            f"- **{r['kind']}** `{r['keyword']}`: {r['reason']} Consider: {consider}."
            f"{blocked}{packed} Evidence: {_ids(r['evidence_ids'])}"
        )
    w("")

    w("## Proposals")
    w("")
    plan = d["backend_plan"]
    if plan and not d["proposals"]:
        w(f"No backend proposal: {plan['note']}.")
    for p in d["proposals"]:
        v = p["validation"]
        w(f"### `{p['id']}`: {p['target_field']} ({p['basis']})")
        w("")
        w(p["rationale"])
        w("")
        value = p["value"] if isinstance(p["value"], str) else " | ".join(p["value"])
        w(f"Proposed value: `{value}`")
        w("")
        w(f"Validation: **{'VALID' if v['valid'] else 'INVALID'}**")
        for problem in v["problems"]:
            w(f"- problem: {problem}")
        if v["missing_evidence"]:
            w(f"- missing evidence: {', '.join(v['missing_evidence'])}")
        for f in v["blocking_findings"]:
            w(f"- blocking `{f['rule_id']}`: {f['message']}")
        for f in v["warnings"]:
            w(f"- warning `{f['rule_id']}`: {f['message']}")
        w("")
        w(f"Evidence: {_ids(p['evidence_ids'], 8)}")
        w("")
    return "\n".join(out).rstrip() + "\n"
