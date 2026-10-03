"""ResearchRun integration of keyword families, judgments and review themes."""

from pathlib import Path

import pytest

from atlas_amazon.evidence import InMemoryEvidenceStore
from atlas_amazon.judgments import JudgmentRequest, JudgmentType, judgment_evidence
from atlas_amazon.planner.recommend import RecommendationKind
from atlas_amazon.research import ResearchConfig, ResearchProviders, TaskStatus, load_scenario
from conftest import T0

SCENARIOS = Path(__file__).parent / "fixtures" / "scenarios"


def scenario(name):
    return load_scenario(SCENARIOS / f"{name}.json")


@pytest.fixture(scope="module")
def bottle():
    return scenario("physical_water_bottle").run()


@pytest.fixture(scope="module")
def book():
    return scenario("book_cozy_mystery").run()


class TestFamiliesChangeRecommendations:
    def test_grouping_removes_a_redundant_gap(self):
        sc = scenario("physical_water_bottle")
        grouped = sc.run()
        flat = sc.run(config=ResearchConfig(keyword_families=False))

        def gaps(result):
            return {
                x.keyword
                for x in result.recommendations
                if x.kind is RecommendationKind.KEYWORD_GAP
            }

        # Without families both orderings are separate gaps; with families they are one.
        assert {"insulated water bottle", "water bottle insulated"} <= gaps(flat)
        assert "insulated water bottle" in gaps(grouped)
        assert "water bottle insulated" not in gaps(grouped)
        rec = next(x for x in grouped.recommendations if x.keyword == "insulated water bottle")
        assert rec.family_members == ("insulated water bottle", "water bottle insulated")
        assert {x.keyword for x in grouped.recommendations} != {
            x.keyword for x in flat.recommendations
        }

    def test_family_aggregation_does_not_double_count(self, bottle):
        d = bottle.derivation("insulated water bottle")
        demand = d.signals.demand
        assert len(demand.evidence_ids) == 2  # one metric per member, each counted once
        assert "120000 + 20000 = 140000" in d.notes["demand"]
        cov = d.signals.competitor_coverage
        assert cov.evidence_ids == tuple(dict.fromkeys(cov.evidence_ids))
        assert "any of 2 member phrases" in d.notes["competitor_coverage"]

    def test_reports_still_show_individual_phrases(self, bottle):
        from atlas_amazon.report import report_dict

        d = report_dict(bottle)
        row = next(k for k in d["ranked_keywords"] if k["keyword"] == "insulated water bottle")
        assert row["family_members"] == ["insulated water bottle", "water bottle insulated"]
        assert {c["keyword"] for c in d["candidates"]} >= {
            "water bottle insulated",
            "kids water bottle",
        }

    def test_packing_skips_redundant_members(self, bottle):
        plan = bottle.backend_plan
        assert set(plan.redundant_members) == {"water bottle insulated", "kids water bottle"}
        assert "redundant family member" in bottle.proposals[0].rationale

    def test_judgment_confirmed_and_rejected_pairs(self, bottle):
        kids = bottle.families.family_of("water bottles for kids")
        assert kids.phrases == ("water bottles for kids", "kids water bottle")
        assert kids.links[0].rule.value == "judgment"
        assert kids.links[0].evidence_ids[0] in kids.evidence_ids
        [rejected] = bottle.families.rejected
        assert {rejected.a, rejected.b} == {"water bottle", "bottle water"}
        assert len(bottle.families.family_of("bottle water").members) == 1


class TestJudgmentIntegration:
    def test_sources_are_explicit(self, bottle):
        top = bottle.derivation("insulated water bottle")
        assert top.sources["relevance"].value == "judgment"
        assert top.sources["intent"].value == "judgment"
        assert top.intent_label == "transactional"
        assert top.signals.relevance.evidence_ids  # judgment evidence cited
        fallback = bottle.derivation("bpa free")
        assert fallback.sources["relevance"].value == "heuristic"
        assert fallback.notes["relevance"].startswith("heuristic:")
        assert fallback.signals.relevance.evidence_ids == ()

    def test_judged_relevance_changes_ranking(self, book):
        ranks = {s.keyword: i for i, s in enumerate(book.ranked)}
        assert ranks["harbor town"] == len(book.ranked) - 1  # judged 0.2: now last

    def test_without_provider_everything_falls_back(self):
        sc = scenario("physical_water_bottle")
        no_judge = ResearchProviders(
            **{
                **{
                    r: getattr(sc.providers, r)
                    for r in ("catalog", "keywords", "suggestions", "reviews", "review_themes")
                },
                "judgments": None,
            }
        )
        result = type(sc)(sc.name, sc.run_id, sc.started_at, sc.product, sc.listing, no_judge).run()
        assert result.semantic_tasks[0].status is TaskStatus.NO_PROVIDER
        assert result.judgments == () and result.entity_flags == ()
        for d in result.derivations:
            assert d.sources["relevance"].value == "heuristic"
        assert result.families.unconfirmed  # pairs stay unconfirmed, not guessed

    def test_entity_flags_block_backend_and_recommendations(self, bottle, book):
        assert [(f.keyword, f.label) for f in bottle.entity_flags] == [
            ("hydra water bottle", "brand")
        ]
        assert "hydra" not in bottle.proposals[0].value.split()
        assert "hydra water bottle" not in {x.keyword for x in bottle.recommendations}
        book_flags = {f.keyword: f.label for f in book.entity_flags}
        assert book_flags == {
            "agatha christie cozy mystery": "author",
            "cozy mystery kindle unlimited": "trademark",
        }
        assert not any("christie" in slot for slot in book.proposals[0].value)
        assert not set(book_flags) & {x.keyword for x in book.recommendations}

    def test_invalid_and_unrequested_judgments_are_ignored(self):
        sc = scenario("partial_missing_data")

        class SloppyJudge:
            name = "sloppy"

            def judge(self, requests, *, marketplace, run_id=None):
                good = (
                    judgment_evidence(
                        provider=self.name,
                        request=requests[0],
                        result={"score": 0.9},
                        confidence=0.9,
                        model="m",
                        prompt_version="p",
                        rationale="ok",
                        marketplace=marketplace,
                        judged_at=T0,
                        run_id=run_id,
                    )
                    if requests[0].type is JudgmentType.RELEVANCE
                    else None
                )
                stray = judgment_evidence(
                    provider=self.name,
                    request=JudgmentRequest.about_keyword(
                        JudgmentType.RELEVANCE, "never asked", product_title="x"
                    ),
                    result={"score": 1.0},
                    confidence=1.0,
                    model="m",
                    prompt_version="p",
                    rationale="unprompted",
                    marketplace=marketplace,
                    judged_at=T0,
                    run_id=run_id,
                )
                return [e for e in (good, stray) if e is not None]

        providers = ResearchProviders(
            catalog=sc.providers.catalog, keywords=sc.providers.keywords, judgments=SloppyJudge()
        )
        store = InMemoryEvidenceStore()
        result = type(sc)(sc.name, sc.run_id, sc.started_at, sc.product, sc.listing, providers).run(
            store=store
        )
        reasons = [r for _, r in result.invalid_judgments]
        assert "answers a request that was not made" in reasons
        assert all(eid in store for eid, _ in result.invalid_judgments)  # stored, not used
        top = result.derivation("yoga mat")
        assert top.sources["relevance"].value == "judgment"
        assert top.sources["intent"].value == "heuristic"


class TestReviewThemesInRun:
    def test_themes_collected_after_reviews_and_summarized(self, bottle):
        task = next(t for t in bottle.tasks if t.task == "competitor_reviews")
        assert "fixture" in task.providers and "3 review themes" in task.note
        themes = bottle.review_themes
        assert [i.theme.theme for i in themes.complaints] == ["lid leaks"]
        assert [i.theme.theme for i in themes.positives] == ["keeps drinks cold all day"]
        assert themes.opportunities[0].first_party_support == ("Leak proof lid with carry loop",)

    def test_book_themes(self, book):
        themes = book.review_themes
        assert [i.theme.theme for i in themes.positives] == ["clean read (no gore or swearing)"]
        assert [i.theme.theme for i in themes.complaints] == ["predictable killer"]
        praise = next(o for o in themes.opportunities if o.basis == "competitor_praise")
        assert praise.first_party_support == ("Clean read with no gore or profanity",)
        complaint = next(o for o in themes.opportunities if o.basis == "competitor_complaint")
        assert complaint.first_party_support == ()  # no claim about our book

    def test_no_theme_provider_means_no_theme_report(self):
        result = scenario("partial_missing_data").run()
        assert result.review_themes is None
