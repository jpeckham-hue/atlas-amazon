"""Deterministic listing audit primitives.

The pure helpers (`find_*`, `check_field_limits`) know nothing about recipes.
`audit_listing` runs a listing against a recipe: required fields, field
limits, then every enabled rule through the `CHECKS` registry. Each Finding
carries the recipe's dated SourceRef, so a reviewer can see which rule (and
how old a rule) produced it.

Semantic judgments, such as an author name in KDP keywords or a misleading
claim, are deliberately absent. They belong to the LLM/human review layer.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable

from atlas_amazon.keywords.coverage import contains_phrase
from atlas_amazon.keywords.normalize import fold_plural, keyword_key, normalize_text, tokenize
from atlas_amazon.models import AuditReport, FieldValue, Finding, Listing, Severity
from atlas_amazon.recipes.schema import FieldSpec, Recipe, RuleSpec

# ---------------------------------------------------------------------------
# Pure helpers


def find_repeated_words(text: str, max_repeats: int, exempt: Iterable[str] = ()) -> dict[str, int]:
    """Normalized words occurring more than `max_repeats` times, in first-seen order."""
    skip = {normalize_text(w) for w in exempt}
    counts = Counter(t for t in tokenize(text) if t not in skip)
    return {word: n for word, n in counts.items() if n > max_repeats}


def find_terms(text: str, terms: Iterable[str]) -> list[str]:
    """Terms whose plural-folded phrase occurs in `text`, in the order given."""
    folded = [fold_plural(t) for t in tokenize(text)]
    return [term for term in terms if contains_phrase(folded, keyword_key(term))]


def find_disallowed_characters(text: str, characters: str) -> list[str]:
    return [ch for ch in dict.fromkeys(text) if ch in characters]


def _length_findings(
    rule_prefix: str,
    label: str,
    text: str,
    max_chars: int | None,
    max_bytes: int | None,
    spec: FieldSpec,
) -> list[Finding]:
    findings = []
    chars = len(text)
    if max_chars is not None and chars > max_chars:
        findings.append(
            Finding(
                rule_id=f"{rule_prefix}.max_chars",
                severity=Severity.ERROR,
                message=f"{label} is {chars} characters (limit {max_chars})",
                field=spec.name,
                observed=chars,
                limit=max_chars,
                source=spec.source,
            )
        )
    size = len(text.encode("utf-8"))
    if max_bytes is not None and size > max_bytes:
        findings.append(
            Finding(
                rule_id=f"{rule_prefix}.max_bytes",
                severity=Severity.ERROR,
                message=f"{label} is {size} bytes (limit {max_bytes})",
                field=spec.name,
                observed=size,
                limit=max_bytes,
                source=spec.source,
            )
        )
    return findings


def check_field_limits(value: FieldValue, spec: FieldSpec) -> list[Finding]:
    """Shape, length, byte and count limits for one field value."""
    name = spec.name
    prefix = f"field_limit.{name}"
    if spec.kind == "text":
        if not isinstance(value, str):
            return [Finding(f"{prefix}.kind", Severity.ERROR, f"{name} must be text", field=name)]
        return _length_findings(prefix, name, value, spec.max_chars, spec.max_bytes, spec)

    if isinstance(value, str):
        return [Finding(f"{prefix}.kind", Severity.ERROR, f"{name} must be a list", field=name)]
    findings = []
    count = len(value)
    if spec.max_count is not None and count > spec.max_count:
        findings.append(
            Finding(
                f"{prefix}.max_count",
                Severity.ERROR,
                f"{name} has {count} items (limit {spec.max_count})",
                field=name,
                observed=count,
                limit=spec.max_count,
                source=spec.source,
            )
        )
    if spec.min_count is not None and count < spec.min_count:
        findings.append(
            Finding(
                f"{prefix}.min_count",
                Severity.ERROR,
                f"{name} has {count} items (minimum {spec.min_count})",
                field=name,
                observed=count,
                limit=spec.min_count,
                source=spec.source,
            )
        )
    for i, item in enumerate(value):
        findings += _length_findings(
            f"{prefix}.item", f"{name}[{i}]", item, spec.item_max_chars, spec.item_max_bytes, spec
        )
    return findings


# ---------------------------------------------------------------------------
# Rule checks: (listing, rule, recipe) -> findings


def _finding(rule: RuleSpec, field: str | None, message: str, observed=None, limit=None) -> Finding:
    return Finding(
        rule_id=rule.id,
        severity=rule.severity,
        message=message,
        field=field,
        observed=observed,
        limit=limit,
        source=rule.source,
    )


def _check_word_repetition(listing: Listing, rule: RuleSpec, recipe: Recipe) -> list[Finding]:
    limit = rule.params["max_repeats"]
    findings = []
    for name in rule.fields:
        repeated = find_repeated_words(listing.text(name), limit, rule.params.get("exempt", ()))
        if repeated:
            words = ", ".join(f"{w!r}x{n}" for w, n in repeated.items())
            findings.append(
                _finding(
                    rule, name, f"words repeated more than {limit} times: {words}", repeated, limit
                )
            )
    return findings


def _check_prohibited_terms(listing: Listing, rule: RuleSpec, recipe: Recipe) -> list[Finding]:
    findings = []
    for name in rule.fields:
        for segment in listing.segments(name):
            hits = find_terms(segment, rule.params["terms"])
            if hits:
                findings.append(_finding(rule, name, f"prohibited terms: {hits}", hits))
    return findings


def _check_disallowed_characters(listing: Listing, rule: RuleSpec, recipe: Recipe) -> list[Finding]:
    findings = []
    for name in rule.fields:
        found = find_disallowed_characters(listing.text(name), rule.params["characters"])
        if found:
            findings.append(_finding(rule, name, f"disallowed characters: {found}", found))
    return findings


def _check_combined_length(listing: Listing, rule: RuleSpec, recipe: Recipe) -> list[Finding]:
    limit = rule.params["max_chars"]
    total = sum(len(listing.text(name)) for name in rule.fields)
    if total <= limit:
        return []
    joined = " + ".join(rule.fields)
    return [_finding(rule, None, f"{joined} is {total} characters (limit {limit})", total, limit)]


def _check_backend_redundancy(listing: Listing, rule: RuleSpec, recipe: Recipe) -> list[Finding]:
    assert recipe.backend is not None  # guaranteed by the loader
    backend = recipe.backend.field_name
    stop = {fold_plural(t) for w in recipe.backend.stopwords for t in tokenize(w)}
    visible = {
        fold_plural(t)
        for name in rule.params["visible_fields"]
        for seg in listing.segments(name)
        for t in tokenize(seg)
    }
    in_visible: dict[str, None] = {}
    repeated: dict[str, None] = {}
    seen: set[str] = set()
    for segment in listing.segments(backend):
        for token in tokenize(segment):
            key = fold_plural(token)
            if key in stop:
                continue
            if key in visible:
                in_visible[token] = None
            if key in seen:
                repeated[token] = None
            seen.add(key)
    findings = []
    if in_visible:
        words = list(in_visible)
        findings.append(_finding(rule, backend, f"backend repeats visible words: {words}", words))
    if repeated:
        words = list(repeated)
        findings.append(_finding(rule, backend, f"backend repeats its own words: {words}", words))
    return findings


CheckFn = Callable[[Listing, RuleSpec, Recipe], list[Finding]]

CHECKS: dict[str, CheckFn] = {
    "word_repetition": _check_word_repetition,
    "prohibited_terms": _check_prohibited_terms,
    "disallowed_characters": _check_disallowed_characters,
    "combined_length": _check_combined_length,
    "backend_redundancy": _check_backend_redundancy,
}


def _is_empty(value: FieldValue) -> bool:
    return not value.strip() if isinstance(value, str) else not any(v.strip() for v in value)


def audit_listing(listing: Listing, recipe: Recipe) -> AuditReport:
    findings: list[Finding] = []
    for name in listing.fields:
        if name not in recipe.fields:
            findings.append(
                Finding(
                    f"unknown_field.{name}",
                    Severity.INFO,
                    f"field {name!r} is not defined by recipe {recipe.id!r}; it was not audited",
                    field=name,
                )
            )
    for name, spec in recipe.fields.items():
        value = listing.fields.get(name)
        if value is None or _is_empty(value):
            if spec.required:
                findings.append(
                    Finding(
                        f"required.{name}",
                        Severity.ERROR,
                        f"required field {name!r} is missing",
                        field=name,
                        source=spec.source,
                    )
                )
            continue
        findings += check_field_limits(value, spec)
    for rule in recipe.enabled_rules():
        findings += CHECKS[rule.check](listing, rule, recipe)
    return AuditReport(recipe_id=recipe.id, findings=tuple(findings))
