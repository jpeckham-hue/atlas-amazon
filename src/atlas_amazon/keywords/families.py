"""Keyword families: phrases that are effectively the same search concept.

Grouping never discards anything. A family keeps every original phrase (a
`KeywordCandidate` with its own sources and evidence), every link explaining
why two phrases were joined, and a canonical label.

Before families, `build_candidates` already merges phrases with the same
plural-folded key ("water bottle" / "Water Bottles!").

**Deterministic links** (applied automatically, because meaning is preserved):

* `stopword_variant`: the same content words in the same order, where one
  phrase only adds connecting words the other lacks ("water bottle for kids"
  ~ "water bottle kids"). *Substituting* connecting words is not a variant
  ("mug for tea" vs "mug with tea").
* `attribute_rotation`: an attribute-like block (1-2 words) moves between
  the front and the back of an intact core of at least 2 words
  ("insulated water bottle" ~ "water bottle insulated"; "32 oz water
  bottle" ~ "water bottle 32 oz"). Attribute-like means a number, a unit, a
  listed attribute word, or a typical adjective suffix (-ed, -less, -proof,
  -free, -able, -ible, -ful, -ous) on a word of 5+ letters. A two-word block
  qualifies when both words are attribute-like ("32 oz"), when it ends in a
  compound head ("leak proof", "bpa free"), or when it starts with an
  attribute-like word ("stainless steel").

**Candidate pairs** (never grouped automatically): the same content words
in a different order, failing the rules above. Swapping nouns can change the
product ("bottle water" vs "water bottle"; "bowl dog food" vs "dog food
bowl"). Such a pair is grouped only when an `equivalence` judgment says so
with confidence >= the threshold. Otherwise it is reported as unconfirmed,
or as rejected by the judgment.

**Canonical label**: the member with the highest search volume, if any
member has one; otherwise (or on ties) the fewest words, then the shortest
text, then alphabetical. The family *ID* hashes the sorted member keys, so
it doesn't depend on which label wins.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from atlas_amazon.jsonvalue import canonical_json
from atlas_amazon.judgments.contract import Judgment, JudgmentType
from atlas_amazon.keywords.candidates import EDGE_STOPWORDS, KeywordCandidate
from atlas_amazon.keywords.normalize import fold_plural, tokenize

ATTRIBUTE_SUFFIXES = ("ed", "less", "proof", "free", "able", "ible", "ful", "ous")
MIN_SUFFIX_WORD = 5
ATTRIBUTE_WORDS = frozenset(
    {
        "large",
        "small",
        "mini",
        "big",
        "thick",
        "thin",
        "lightweight",
        "resistant",
        "organic",
        "natural",
        "wireless",
        "electric",
        "manual",
        "automatic",
        "cordless",
    }
)
UNIT_WORDS = frozenset(
    {
        "oz",
        "ounce",
        "ml",
        "l",
        "liter",
        "litre",
        "gallon",
        "inch",
        "in",
        "cm",
        "mm",
        "ft",
        "lb",
        "lbs",
        "kg",
        "g",
        "pack",
        "count",
        "pc",
        "pcs",
        "piece",
    }
)
# Words that make a two-word block an attribute compound ("leak proof", "bpa free").
# Only used inside two-word blocks; on their own they are not treated as attributes.
COMPOUND_ATTRIBUTE_HEADS = frozenset({"proof", "free", "resistant", "safe"})
MAX_ROTATED_BLOCK = 2
MIN_CORE = 2


class EquivalenceRule(StrEnum):
    STOPWORD_VARIANT = "stopword_variant"
    ATTRIBUTE_ROTATION = "attribute_rotation"
    JUDGMENT = "judgment"


@dataclass(frozen=True, slots=True)
class EquivalenceLink:
    a: str
    b: str
    rule: EquivalenceRule
    detail: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PairCandidate:
    """Same words, different order, not provably equivalent."""

    a: str
    b: str
    detail: str
    judgment_id: str | None = None  # set when a judgment rejected the pair
    judgment_note: str = ""


@dataclass(frozen=True, slots=True)
class KeywordFamily:
    id: str
    canonical: str
    canonical_reason: str
    members: tuple[KeywordCandidate, ...]
    links: tuple[EquivalenceLink, ...]

    @property
    def phrases(self) -> tuple[str, ...]:
        return tuple(m.keyword for m in self.members)

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        """Every member's evidence plus the evidence for any judgment link, deduplicated."""
        ids: dict[str, None] = {}
        for member in self.members:
            ids.update(dict.fromkeys(member.evidence_ids))
        for link in self.links:
            ids.update(dict.fromkeys(link.evidence_ids))
        return tuple(ids)

    def member(self, phrase: str) -> KeywordCandidate:
        for m in self.members:
            if m.keyword == phrase:
                return m
        raise KeyError(phrase)


@dataclass(frozen=True, slots=True)
class FamilyGrouping:
    families: tuple[KeywordFamily, ...]
    unconfirmed: tuple[PairCandidate, ...]  # no judgment available
    rejected: tuple[PairCandidate, ...]  # a judgment said "not equivalent" (or low confidence)

    def family_of(self, phrase: str) -> KeywordFamily:
        for family in self.families:
            if phrase in family.phrases:
                return family
        raise KeyError(phrase)


def _content(tokens: Sequence[str]) -> list[str]:
    return [fold_plural(t) for t in tokens if t not in EDGE_STOPWORDS]


def _attribute_reason(token: str) -> str | None:
    if token.isdigit():
        return "number"
    if token in UNIT_WORDS:
        return "unit"
    if token in ATTRIBUTE_WORDS:
        return "attribute word"
    if len(token) >= MIN_SUFFIX_WORD:
        for suffix in ATTRIBUTE_SUFFIXES:
            if token.endswith(suffix) and token != suffix:
                return f"suffix -{suffix}"
    return None


def _block_reason(block: Sequence[str]) -> str | None:
    if len(block) == 1:
        return _attribute_reason(block[0])
    reasons = [_attribute_reason(t) for t in block]
    if all(reasons):
        return " + ".join(reasons)  # e.g. number + unit
    if block[-1] in COMPOUND_ATTRIBUTE_HEADS:
        return f"attribute compound ending in '{block[-1]}'"  # leak proof, bpa free
    if reasons[0]:
        return f"attribute compound starting with '{block[0]}' ({reasons[0]})"  # stainless steel
    return None


def relate(a: str, b: str) -> tuple[EquivalenceRule | None, str, bool]:
    """(rule, detail, is_candidate_pair) for two normalized phrases."""
    ta, tb = tokenize(a), tokenize(b)
    ca, cb = _content(ta), _content(tb)
    # Same plural-folded key means the same candidate (merged upstream), not a family link.
    if not ca or not cb or [fold_plural(t) for t in ta] == [fold_plural(t) for t in tb]:
        return None, "", False
    if ca == cb:
        sa = Counter(t for t in ta if t in EDGE_STOPWORDS)
        sb = Counter(t for t in tb if t in EDGE_STOPWORDS)
        if sa <= sb or sb <= sa:
            diff = sorted(((sa - sb) + (sb - sa)).elements())
            return (
                EquivalenceRule.STOPWORD_VARIANT,
                f"same words in the same order; differ only by {diff}",
                False,
            )
        return None, "same words, but different connecting words", True
    if sorted(ca) != sorted(cb) or len(ca) < 2:
        return None, "", False
    for k in range(1, MAX_ROTATED_BLOCK + 1):
        if len(ca) - k < MIN_CORE:
            continue
        for x, y in ((ca, cb), (cb, ca)):
            # A block at the front of x appears at the back of y.
            if y == x[k:] + x[:k]:
                block, core = x[:k], x[k:]
                reason = _block_reason(block)
                if reason:
                    return (
                        EquivalenceRule.ATTRIBUTE_ROTATION,
                        f"'{' '.join(block)}' ({reason}) moved around the intact core "
                        f"'{' '.join(core)}'",
                        False,
                    )
    return None, "same words in a different order; order may change meaning", True


def _canonical(members: Sequence[KeywordCandidate], volumes: Mapping[tuple[str, ...], float]):
    def sort_key(m: KeywordCandidate):
        volume = volumes.get(m.key)
        return (-(volume if volume is not None else -1), len(m.key), len(m.keyword), m.keyword)

    best = min(members, key=sort_key)
    volume = volumes.get(best.key)
    if len(members) == 1:
        reason = "single member"
    elif volume is not None:
        reason = f"highest search volume among members ({volume:g})"
    else:
        reason = "no member has search volume: fewest words, then shortest"
    return best, reason


def _family_id(members: Sequence[KeywordCandidate]) -> str:
    keys = sorted(" ".join(m.key) for m in members)
    return "fam_" + hashlib.sha256(canonical_json(keys).encode("utf-8")).hexdigest()[:16]


def group_keyword_families(
    candidates: Sequence[KeywordCandidate],
    *,
    volumes: Mapping[tuple[str, ...], float] | None = None,
    equivalence: Sequence[Judgment] = (),
    min_confidence: float = 0.7,
    enabled: bool = True,
) -> FamilyGrouping:
    volumes = volumes or {}
    n = len(candidates)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    links: list[tuple[int, int, EquivalenceLink]] = []
    unconfirmed: list[PairCandidate] = []
    rejected: list[PairCandidate] = []
    judged = {
        tuple(j.input["phrases"]): j for j in equivalence if j.type is JudgmentType.EQUIVALENCE
    }

    if enabled:
        for i in range(n):
            for j in range(i + 1, n):
                a, b = candidates[i].keyword, candidates[j].keyword
                rule, detail, is_pair = relate(a, b)
                link = None
                if rule is not None:
                    link = EquivalenceLink(a, b, rule, detail)
                elif is_pair:
                    judgment = judged.get(tuple(sorted((a, b))))
                    if judgment is None:
                        unconfirmed.append(PairCandidate(a, b, detail))
                        continue
                    confidence = judgment.confidence
                    accepted = judgment.result["equivalent"] and (
                        confidence is not None and confidence >= min_confidence
                    )
                    if accepted:
                        link = EquivalenceLink(
                            a,
                            b,
                            EquivalenceRule.JUDGMENT,
                            f"equivalence judgment ({judgment.model}, "
                            f"{judgment.prompt_version}, confidence {confidence}): "
                            f"{judgment.rationale}",
                            (judgment.evidence_id,),
                        )
                    else:
                        why = (
                            "judged not equivalent"
                            if not judgment.result["equivalent"]
                            else f"confidence {confidence} below {min_confidence}"
                        )
                        rejected.append(
                            PairCandidate(
                                a, b, detail, judgment.evidence_id, f"{why}: {judgment.rationale}"
                            )
                        )
                        continue
                if link is not None:
                    links.append((i, j, link))
                    parent[find(j)] = find(i)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    families = []
    for root in sorted(groups, key=lambda r: min(groups[r])):
        indexes = sorted(groups[root])
        members = tuple(candidates[i] for i in indexes)
        member_set = set(indexes)
        family_links = tuple(link for i, j, link in links if i in member_set)
        best, reason = _canonical(members, volumes)
        families.append(
            KeywordFamily(_family_id(members), best.keyword, reason, members, family_links)
        )
    return FamilyGrouping(tuple(families), tuple(unconfirmed), tuple(rejected))


def singleton_families(candidates: Sequence[KeywordCandidate]) -> tuple[KeywordFamily, ...]:
    """One family per candidate, with no grouping (families disabled)."""
    return group_keyword_families(candidates, enabled=False).families
