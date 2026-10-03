from datetime import UTC, datetime

import pytest

from atlas_amazon.judgments import JudgmentRequest, judgment_evidence, parse_judgment
from atlas_amazon.keywords.candidates import CandidateSource, KeywordCandidate
from atlas_amazon.keywords.families import (
    EquivalenceRule,
    group_keyword_families,
    relate,
    singleton_families,
)
from atlas_amazon.keywords.normalize import keyword_key, normalize_text

T = datetime(2026, 10, 3, tzinfo=UTC)


def cand(phrase, *ids):
    text = normalize_text(phrase)
    return KeywordCandidate(text, keyword_key(text), (CandidateSource.SUGGESTION,), tuple(ids))


def equivalence(a, b, equivalent, confidence=0.9):
    request = JudgmentRequest.equivalence(a, b)
    return parse_judgment(
        judgment_evidence(
            provider="fx",
            request=request,
            result={"equivalent": equivalent},
            confidence=confidence,
            model="m",
            prompt_version="p",
            rationale="because",
            marketplace="US",
            judged_at=T,
        )
    )


class TestRelate:
    @pytest.mark.parametrize(
        ("a", "b", "rule"),
        [
            ("insulated water bottle", "water bottle insulated", "attribute_rotation"),
            ("water bottle 32 oz", "32 oz water bottle", "attribute_rotation"),
            ("leak proof water bottle", "water bottle leak proof", "attribute_rotation"),
            ("stainless steel water bottle", "water bottle stainless steel", "attribute_rotation"),
            ("water bottle bpa free", "bpa free water bottle", "attribute_rotation"),
            ("water bottle for kids", "water bottle kids", "stopword_variant"),
            ("bottle of water", "bottle water", "stopword_variant"),
        ],
    )
    def test_true_equivalents(self, a, b, rule):
        found, detail, is_pair = relate(a, b)
        assert found == EquivalenceRule(rule)
        assert detail and not is_pair
        assert relate(b, a)[0] == found  # symmetric

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            ("water bottle", "bottle water"),  # noun swap changes the product
            ("dog food bowl", "bowl dog food"),  # head noun moved
            ("kids water bottle", "water bottle for kids"),  # plausible, but needs a judgment
            ("mug for tea", "mug with tea"),  # different connecting words
            ("small town mystery", "mystery small town"),
            ("speed bag", "bag speed"),  # 'speed' ends in -ed, but there is no 2-word core
        ],
    )
    def test_near_equivalents_need_a_judgment(self, a, b):
        rule, detail, is_pair = relate(a, b)
        assert rule is None and is_pair and detail

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            ("cozy mystery", "cozy mystery books"),  # different specificity
            ("small town mystery", "small town murder mystery"),
            ("water bottle", "water bottles"),  # same key: merged earlier, not a family link
            ("insulated mug", "insulated bottle"),
            ("for the", "the for"),  # no content words
        ],
    )
    def test_must_remain_separate(self, a, b):
        rule, _, is_pair = relate(a, b)
        assert rule is None and not is_pair


class TestGrouping:
    def test_preserves_every_phrase_and_its_evidence(self):
        a, b, c = (
            cand("insulated water bottle", "ev_a"),
            cand("water bottle insulated", "ev_b"),
            cand("coffee mug", "ev_c"),
        )
        grouping = group_keyword_families([a, b, c], volumes={a.key: 100.0, b.key: 900.0})
        fam = grouping.family_of("insulated water bottle")
        assert fam.phrases == ("insulated water bottle", "water bottle insulated")
        assert fam.member("water bottle insulated").evidence_ids == ("ev_b",)
        assert fam.evidence_ids == ("ev_a", "ev_b")
        assert fam.canonical == "water bottle insulated"  # highest volume wins
        assert "highest search volume" in fam.canonical_reason
        [link] = fam.links
        assert link.rule is EquivalenceRule.ATTRIBUTE_ROTATION
        assert grouping.family_of("coffee mug").phrases == ("coffee mug",)

    def test_canonical_without_volumes_prefers_fewer_words(self):
        grouping = group_keyword_families(
            [cand("water bottle for kids"), cand("water bottle kids")]
        )
        assert grouping.families[0].canonical == "water bottle kids"
        assert "no member has search volume" in grouping.families[0].canonical_reason

    def test_family_id_is_independent_of_order_and_label(self):
        a, b = cand("insulated water bottle"), cand("water bottle insulated")
        one = group_keyword_families([a, b], volumes={a.key: 1.0}).families[0]
        two = group_keyword_families([b, a], volumes={b.key: 1.0}).families[0]
        assert one.id == two.id and one.canonical != two.canonical

    def test_transitive_grouping(self):
        phrases = [
            "insulated water bottle",
            "water bottle insulated",
            "insulated water bottles for",
            "water bottle for insulated",
        ]
        grouping = group_keyword_families([cand(p) for p in phrases[:3]])
        assert len(grouping.families) == 1

    def test_unconfirmed_pairs_stay_separate(self):
        grouping = group_keyword_families([cand("water bottle"), cand("bottle water")])
        assert len(grouping.families) == 2
        [pair] = grouping.unconfirmed
        assert (pair.a, pair.b) == ("water bottle", "bottle water")

    def test_judgment_confirms_pair_with_evidence(self):
        j = equivalence("kids water bottle", "water bottle for kids", True)
        grouping = group_keyword_families(
            [cand("kids water bottle"), cand("water bottle for kids")], equivalence=[j]
        )
        fam = grouping.families[0]
        assert len(grouping.families) == 1 and not grouping.unconfirmed
        assert fam.links[0].rule is EquivalenceRule.JUDGMENT
        assert fam.links[0].evidence_ids == (j.evidence_id,)
        assert j.evidence_id in fam.evidence_ids

    @pytest.mark.parametrize(
        ("equivalent", "confidence", "why"),
        [
            (False, 0.99, "judged not equivalent"),
            (True, 0.5, "below 0.7"),
            (True, None, "below 0.7"),
        ],
    )
    def test_judgment_rejections_are_recorded(self, equivalent, confidence, why):
        j = equivalence("water bottle", "bottle water", equivalent, confidence)
        grouping = group_keyword_families(
            [cand("water bottle"), cand("bottle water")], equivalence=[j]
        )
        assert len(grouping.families) == 2
        [rejected] = grouping.rejected
        assert rejected.judgment_id == j.evidence_id
        assert why in rejected.judgment_note

    def test_judgments_cannot_join_unrelated_phrases(self):
        j = equivalence("coffee mug", "tea cup", True)
        grouping = group_keyword_families([cand("coffee mug"), cand("tea cup")], equivalence=[j])
        assert len(grouping.families) == 2  # only same-word pairs are ever considered

    def test_disabled_and_singletons(self):
        cands = [cand("insulated water bottle"), cand("water bottle insulated")]
        assert len(group_keyword_families(cands, enabled=False).families) == 2
        assert [f.phrases for f in singleton_families(cands)] == [
            ("insulated water bottle",),
            ("water bottle insulated",),
        ]

    def test_deterministic(self):
        cands = [
            cand(p)
            for p in (
                "water bottle",
                "bottle water",
                "insulated water bottle",
                "water bottle insulated",
            )
        ]
        assert group_keyword_families(cands) == group_keyword_families(cands)
