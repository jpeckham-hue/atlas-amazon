"""Render a ResearchResult as a JSON-ready dict or Markdown.

This layer formats, it does not decide. It computes no scores, thresholds,
groupings, rankings or recommendations; it only copies and lays out what
the domain produced. Every derived figure keeps its evidence IDs, and every
relevance/intent value shows its source (judgment or heuristic).
"""

from __future__ import annotations

import json
from typing import Any

from atlas_amazon.jsonvalue import thaw
from atlas_amazon.models import Finding
from atlas_amazon.research.run import ResearchResult
from atlas_amazon.reviews.themes import ThemeInsight

SOURCE_MARK = {"evidence": "", "judgment": " J", "heuristic": " H"}


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


def _insight(i: ThemeInsight) -> dict[str, Any]:
    t = i.theme
    return {
        "theme": t.theme,
        "polarity": t.polarity.value,
        "count": t.count,
        "products": list(t.products),
        "competitor_products": list(i.competitor_products),
        "about_own_product": i.about_own_product,
        "repeated": i.repeated,
        "terms": list(t.terms),
        "extractor": f"{t.extractor} {t.extractor_version}",
        "rationale": t.rationale,
        "theme_evidence_id": t.evidence_id,
        "review_evidence_ids": list(t.review_evidence_ids),
    }


def _task(t) -> dict[str, Any]:
    return {
        "priority": t.priority,
        "task": t.task,
        "status": t.status.value,
        "providers": list(t.providers),
        "evidence_ids": list(t.evidence_ids),
        "new_records": t.new_records,
        "reused_records": t.reused_records,
        "note": t.note,
    }


def report_dict(result: ResearchResult) -> dict[str, Any]:
    m = result.metadata
    ev = result.evidence
    plan = result.backend_plan
    themes = result.review_themes
    family_of = {f.canonical: f for f in result.families.families}
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
                "keyword_families": m.config.keyword_families,
                "min_equivalence_confidence": m.config.min_equivalence_confidence,
                "min_theme_count": m.config.min_theme_count,
            },
            "evidence_fingerprint": m.evidence_fingerprint,
        },
        "tasks": [_task(t) for t in result.tasks],
        "semantic_tasks": [_task(t) for t in result.semantic_tasks],
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
        "families": {
            "groups": [
                {
                    "id": f.id,
                    "canonical": f.canonical,
                    "canonical_reason": f.canonical_reason,
                    "members": list(f.phrases),
                    "links": [
                        {
                            "a": link.a,
                            "b": link.b,
                            "rule": link.rule.value,
                            "detail": link.detail,
                            "evidence_ids": list(link.evidence_ids),
                        }
                        for link in f.links
                    ],
                    "evidence_ids": list(f.evidence_ids),
                }
                for f in result.families.families
                if len(f.members) > 1
            ],
            "unconfirmed_pairs": [
                {"a": p.a, "b": p.b, "detail": p.detail} for p in result.families.unconfirmed
            ],
            "rejected_pairs": [
                {
                    "a": p.a,
                    "b": p.b,
                    "detail": p.detail,
                    "judgment_id": p.judgment_id,
                    "judgment_note": p.judgment_note,
                }
                for p in result.families.rejected
            ],
        },
        "judgments": [
            {
                "evidence_id": j.evidence_id,
                "type": j.type.value,
                "subject": j.subject,
                "result": thaw(j.result),
                "confidence": j.confidence,
                "model": j.model,
                "prompt_version": j.prompt_version,
                "input_hash": j.input_hash,
                "judged_at": j.judged_at.isoformat(),
                "rationale": j.rationale,
            }
            for j in result.judgments
        ],
        "invalid_judgments": [{"evidence_id": i, "reason": r} for i, r in result.invalid_judgments],
        "entity_flags": [
            {
                "keyword": f.keyword,
                "label": f.label,
                "entity": f.entity,
                "judgment_id": f.judgment_id,
            }
            for f in result.entity_flags
        ],
        "ranked_keywords": [
            {
                "rank": rank,
                "keyword": s.keyword,
                "family_id": family_of[s.keyword].id,
                "family_members": list(family_of[s.keyword].phrases),
                "score": s.score,
                "heuristic_signals": list(s.heuristic_signals),
                "judgment_signals": [
                    name
                    for name, src in result.derivation(s.keyword).sources.items()
                    if src.value == "judgment"
                ],
                "intent_label": result.derivation(s.keyword).intent_label,
                "evidence_ids": list(s.evidence_ids),
                "signals": [
                    {
                        "signal": c.signal,
                        "source": result.derivation(s.keyword).sources[c.signal].value,
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
                "family_members": list(d.family.phrases),
                "missing_signals": list(d.missing),
                "notes": {k: d.notes[k] for k in d.missing},
                "evidence_ids": list(d.family.evidence_ids),
            }
            for d in result.unscored
        ],
        "coverage": None
        if result.coverage is None
        else {
            "member_exact_rate": result.coverage.exact_rate,
            "member_token_rate": result.coverage.token_rate,
            "field_weights": dict(result.coverage.field_weights),
            "families": [
                {
                    "keyword": fc.keyword,
                    "members": list(fc.members),
                    "covered": fc.covered,
                    "exact_fields": list(fc.exact_fields),
                    "best_field": fc.best_field,
                    "best_member": fc.best_member,
                    "placement": fc.placement_score,
                }
                for fc in result.family_coverage
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
            "redundant_members": list(plan.redundant_members),
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
                "family_members": list(r.family_members),
                "matched_member": r.matched_member,
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
        "review_themes": None
        if themes is None
        else {
            "min_count": themes.min_count,
            "positives": [_insight(i) for i in themes.positives],
            "complaints": [_insight(i) for i in themes.complaints],
            "other": [_insight(i) for i in themes.other],
            "opportunities": [
                {
                    "theme": o.theme,
                    "basis": o.basis,
                    "statement": o.statement,
                    "first_party_support": list(o.first_party_support),
                    "evidence_ids": list(o.evidence_ids),
                }
                for o in themes.opportunities
            ],
            "invalid": [{"evidence_id": i, "reason": r} for i, r in themes.invalid],
        },
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


def _task_rows(w, tasks) -> None:
    w("| Priority | Task | Status | New / reused | Note |")
    w("|---|---|---|---|---|")
    for t in tasks:
        w(
            f"| {t['priority']} | {t['task'] or '-'} | {t['status']} | "
            f"{t['new_records']} / {t['reused_records']} | {t['note']} |"
        )


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
    w(f"- Keyword families: {'on' if run['config']['keyword_families'] else 'off'}")
    w(f"- Evidence fingerprint: `{run['evidence_fingerprint'][:16]}`")
    w("")

    w("## Research tasks")
    w("")
    _task_rows(w, d["tasks"] + d["semantic_tasks"])
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

    fam = d["families"]
    w("## Keyword families")
    w("")
    if not fam["groups"]:
        w("No multi-phrase families.")
    for g in fam["groups"]:
        w(
            f"- **{g['canonical']}** (`{g['id']}`, canonical: {g['canonical_reason']}): "
            + ", ".join(f"`{p}`" for p in g["members"])
        )
        for link in g["links"]:
            ev_note = f" Evidence: {_ids(link['evidence_ids'])}" if link["evidence_ids"] else ""
            w(f"  - `{link['a']}` ~ `{link['b']}` [{link['rule']}]: {link['detail']}{ev_note}")
    for p in fam["unconfirmed_pairs"]:
        w(f"- Unconfirmed (kept separate, no judgment): `{p['a']}` / `{p['b']}`: {p['detail']}")
    for p in fam["rejected_pairs"]:
        w(
            f"- Kept separate by judgment `{p['judgment_id']}`: `{p['a']}` / `{p['b']}`: "
            f"{p['judgment_note']}"
        )
    w("")

    w("## Ranked keywords")
    w("")
    if not d["ranked_keywords"]:
        w("No keyword had evidence for every required signal.")
    else:
        w(
            "| # | Keyword (family) | Score | Relevance | Demand | Competition (inv.) | Intent | "
            "Competitor coverage |"
        )
        w("|---|---|---|---|---|---|---|---|")
        for k in d["ranked_keywords"]:
            cells = {
                s["signal"]: f"{s['contribution']:.3f}{SOURCE_MARK[s['source']]}"
                for s in k["signals"]
            }
            extra = len(k["family_members"]) - 1
            name = k["keyword"] + (
                f" (+{extra} variant{'s' if extra > 1 else ''})" if extra else ""
            )
            w(
                f"| {k['rank']} | {name} | {k['score']:.3f} | {cells['relevance']} | "
                f"{cells['demand']} | {cells['competition']} | {cells['intent']} | "
                f"{cells['competitor_coverage']} |"
            )
        w("")
        w(
            "Cells show weighted contributions. J = semantic judgment (evidence-backed); "
            "H = heuristic placeholder (no evidence); unmarked = measured evidence."
        )
    w("")

    w("## Signal breakdown")
    w("")
    for k in d["ranked_keywords"]:
        w(f"### {k['rank']}. {k['keyword']}: {k['score']:.3f}")
        w("")
        if len(k["family_members"]) > 1:
            w("Family phrases: " + ", ".join(f"`{p}`" for p in k["family_members"]))
            w("")
        if k["intent_label"]:
            w(f"Intent label (judgment): {k['intent_label']}")
            w("")
        w("| Signal | Source | Raw | Normalized | Weight | Contribution | Evidence | Derivation |")
        w("|---|---|---|---|---|---|---|---|")
        for s in k["signals"]:
            w(
                f"| {s['signal']} | {s['source']} | {s['raw']:.3f} | {s['normalized']:.3f} | "
                f"{s['weight']:.2f} | {s['contribution']:.3f} | {_ids(s['evidence_ids'], 2)} | "
                f"{s['derivation']} |"
            )
        w("")

    if d["unscored_keywords"]:
        w("## Unscored keywords (missing evidence)")
        w("")
        for u in d["unscored_keywords"]:
            reasons = "; ".join(f"{k}: {v}" for k, v in u["notes"].items())
            w(f"- {u['keyword']}: {reasons}")
        w("")

    if d["judgments"] or d["invalid_judgments"] or d["entity_flags"]:
        w("## Semantic judgments")
        w("")
        counts: dict[str, int] = {}
        for j in d["judgments"]:
            counts[j["type"]] = counts.get(j["type"], 0) + 1
        models = sorted({f"{j['model']} ({j['prompt_version']})" for j in d["judgments"]})
        w(
            f"{len(d['judgments'])} valid judgments: "
            + (", ".join(f"{t} {n}" for t, n in sorted(counts.items())) or "none")
            + (f". Models/prompts: {'; '.join(models)}." if models else ".")
        )
        for flag in d["entity_flags"]:
            w(
                f"- Entity flag: `{flag['keyword']}` is a {flag['label']} reference "
                f"({flag['entity']}); kept out of the backend and of listing recommendations. "
                f"Judgment `{flag['judgment_id']}`"
            )
        for bad in d["invalid_judgments"]:
            w(f"- Invalid judgment `{bad['evidence_id']}` (ignored): {bad['reason']}")
        w("")

    themes = d["review_themes"]
    if themes is not None:
        w("## Review themes")
        w("")
        w(f"Repeated means at least {themes['min_count']} supporting reviews.")
        w("")
        for title, items in (
            ("Repeated positive themes", themes["positives"]),
            ("Repeated complaints", themes["complaints"]),
        ):
            w(f"### {title}")
            w("")
            if not items:
                w("None.")
            for t in items:
                own = " (includes our product)" if t["about_own_product"] else ""
                w(
                    f"- **{t['theme']}**: {t['count']} reviews across "
                    f"{', '.join(t['products'])}{own}. Evidence: "
                    f"{_ids([t['theme_evidence_id'], *t['review_evidence_ids']])}"
                )
            w("")
        w("### Possible listing opportunities")
        w("")
        if not themes["opportunities"]:
            w("None.")
        for o in themes["opportunities"]:
            w(f"- {o['statement']} Evidence: {_ids(o['evidence_ids'])}")
        w("")
        if themes["other"]:
            w(
                "Other themes (not repeated, or mixed/neutral): "
                + ", ".join(
                    f"{t['theme']} ({t['polarity']}, {t['count']})" for t in themes["other"]
                )
            )
            w("")
        for bad in themes["invalid"]:
            w(f"- Invalid theme `{bad['evidence_id']}` (ignored): {bad['reason']}")

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
        variants = [p for p in r["family_members"] if p != r["keyword"]]
        family = f" Family variants: {', '.join(variants)}." if variants else ""
        w(
            f"- **{r['kind']}** `{r['keyword']}`: {r['reason']} Consider: {consider}."
            f"{blocked}{family}{packed} Evidence: {_ids(r['evidence_ids'])}"
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
