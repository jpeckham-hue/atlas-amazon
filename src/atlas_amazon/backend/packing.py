"""Deterministic packing of backend keywords into Amazon's hidden-term budgets.

Two budget shapes, chosen by the recipe:

* bytes: one field with a UTF-8 byte budget (e.g. Seller Central "search
  terms"). Packing happens at the word level, because word order and
  repetition don't help there. Words are deduplicated by plural-folded key,
  stopwords and words already visible in the listing are dropped, and the
  rest are added greedily in priority order. A word that doesn't fit is
  skipped, and packing keeps trying later, shorter words.
* slots: N boxes of at most M characters each (e.g. KDP's keyword boxes).
  Phrases stay intact and are placed first-fit in priority order.

Every candidate that isn't packed is returned with a reason, so callers can
always explain why a term was left out.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from atlas_amazon.keywords.normalize import fold_plural, keyword_key, normalize_text, tokenize


class ExclusionReason(StrEnum):
    EMPTY = "empty"
    STOPWORD = "stopword"
    DUPLICATE = "duplicate"
    IN_VISIBLE_LISTING = "in_visible_listing"
    TOO_LONG = "too_long"
    OVER_BUDGET = "over_budget"


@dataclass(frozen=True, slots=True)
class Exclusion:
    term: str
    reason: ExclusionReason
    candidate: str


def backend_byte_length(text: str, *, count_spaces: bool = True) -> int:
    """UTF-8 byte length. Counting spaces is the conservative default."""
    if not count_spaces:
        text = text.replace(" ", "")
    return len(text.encode("utf-8"))


def _folded_tokens(texts: Iterable[str]) -> set[str]:
    return {fold_plural(t) for text in texts for t in tokenize(text)}


@dataclass(frozen=True, slots=True)
class BytePackResult:
    text: str
    byte_count: int
    max_bytes: int
    included: tuple[str, ...]
    excluded: tuple[Exclusion, ...]

    @property
    def remaining_bytes(self) -> int:
        return self.max_bytes - self.byte_count


def pack_backend_bytes(
    candidates: Sequence[str],
    max_bytes: int,
    *,
    visible: Iterable[str] = (),
    stopwords: Iterable[str] = (),
    count_spaces: bool = True,
) -> BytePackResult:
    """Pack candidate terms (highest priority first) into a byte budget."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    stop = _folded_tokens(stopwords)
    shown = _folded_tokens(visible)
    included: list[str] = []
    seen: set[str] = set()
    excluded: list[Exclusion] = []

    for candidate in candidates:
        tokens = tokenize(candidate)
        if not tokens:
            excluded.append(Exclusion(candidate, ExclusionReason.EMPTY, candidate))
            continue
        for token in tokens:
            key = fold_plural(token)
            if key in stop:
                reason = ExclusionReason.STOPWORD
            elif key in seen:
                reason = ExclusionReason.DUPLICATE
            elif key in shown:
                reason = ExclusionReason.IN_VISIBLE_LISTING
            elif (
                backend_byte_length(" ".join([*included, token]), count_spaces=count_spaces)
                > max_bytes
            ):
                reason = ExclusionReason.OVER_BUDGET
            else:
                included.append(token)
                seen.add(key)
                continue
            excluded.append(Exclusion(token, reason, candidate))

    text = " ".join(included)
    return BytePackResult(
        text=text,
        byte_count=backend_byte_length(text, count_spaces=count_spaces),
        max_bytes=max_bytes,
        included=tuple(included),
        excluded=tuple(excluded),
    )


@dataclass(frozen=True, slots=True)
class SlotPackResult:
    slots: tuple[str, ...]
    slot_max_chars: int
    placed: tuple[tuple[str, int], ...]  # (phrase, slot index)
    excluded: tuple[Exclusion, ...]


def pack_keyword_slots(
    candidates: Sequence[str],
    slots: int,
    slot_max_chars: int,
    *,
    visible: Iterable[str] = (),
) -> SlotPackResult:
    """Place whole phrases (highest priority first) into fixed-size keyword boxes.

    A phrase is dropped as IN_VISIBLE_LISTING only if every one of its words
    already appears in the visible text. Otherwise it adds new matching surface.
    """
    if slots <= 0 or slot_max_chars <= 0:
        raise ValueError("slots and slot_max_chars must be positive")
    shown = _folded_tokens(visible)
    boxes: list[list[str]] = [[] for _ in range(slots)]
    lengths = [0] * slots
    seen: set[tuple[str, ...]] = set()
    placed: list[tuple[str, int]] = []
    excluded: list[Exclusion] = []

    for candidate in candidates:
        phrase = normalize_text(candidate)
        key = keyword_key(phrase)
        reason: ExclusionReason | None = None
        if not phrase:
            reason = ExclusionReason.EMPTY
        elif key in seen:
            reason = ExclusionReason.DUPLICATE
        elif shown and all(t in shown for t in key):
            reason = ExclusionReason.IN_VISIBLE_LISTING
        elif len(phrase) > slot_max_chars:
            reason = ExclusionReason.TOO_LONG
        else:
            for i in range(slots):
                needed = len(phrase) + (1 if lengths[i] else 0)
                if lengths[i] + needed <= slot_max_chars:
                    boxes[i].append(phrase)
                    lengths[i] += needed
                    placed.append((phrase, i))
                    seen.add(key)
                    break
            else:
                reason = ExclusionReason.OVER_BUDGET
        if reason is not None:
            excluded.append(Exclusion(phrase or candidate, reason, candidate))

    return SlotPackResult(
        slots=tuple(" ".join(box) for box in boxes),
        slot_max_chars=slot_max_chars,
        placed=tuple(placed),
        excluded=tuple(excluded),
    )
