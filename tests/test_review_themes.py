from datetime import UTC, datetime

import pytest

from atlas_amazon.evidence import make_evidence
from atlas_amazon.models import ProductInput
from atlas_amazon.providers import FixtureData, FixtureReviewThemeProvider, ReviewThemeProvider
from atlas_amazon.reviews import (
    Polarity,
    ReviewThemeError,
    parse_review_theme,
    review_theme_evidence,
    summarize_review_themes,
)

T = datetime(2026, 10, 3, tzinfo=UTC)


def review(asin, index, text="x"):
    return make_evidence(
        provider="fx",
        kind="review_sample",
        marketplace="US",
        retrieved_at=T,
        payload={"asin": asin, "index": index, "rating": 3, "text": text},
        subject=asin,
        run_id="r1",
    )


R = [
    review("B0C0000001", 0),
    review("B0C0000001", 1),
    review("B0C0000002", 0),
    review("B0OWN00001", 0),
]


def theme(name, polarity, reviews, terms=("leak",)):
    return review_theme_evidence(
        provider="fx",
        theme=name,
        polarity=polarity,
        reviews=reviews,
        terms=terms,
        extractor="fixture",
        extractor_version="v1",
        rationale="because",
        marketplace="US",
        run_id="r1",
        extracted_at=T,
    )


PRODUCT = ProductInput(
    "Acme Bottle",
    "physical-product",
    asin="B0OWN00001",
    competitor_asins=("B0C0000001", "B0C0000002"),
    attributes={"features": ["Leak proof lid", "Fits cup holders"]},
)


class TestEvidence:
    def test_counts_and_products_are_derived_from_reviews(self):
        ev = theme("lid leaks", "negative", [R[0], R[2], R[0]])
        assert ev.kind == "review_theme"
        assert ev.payload["count"] == 2  # duplicate review collapsed
        assert ev.payload["products"] == ("B0C0000001", "B0C0000002")
        t = parse_review_theme(ev, {r.id: r for r in R})
        assert t.polarity is Polarity.NEGATIVE
        assert t.review_evidence_ids == (R[0].id, R[2].id)

    def test_requires_supporting_reviews(self):
        with pytest.raises(ReviewThemeError):
            theme("empty", "positive", [])
        with pytest.raises(ValueError):
            theme("bad polarity", "angry", [R[0]])

    def test_parse_rejects_overstated_or_unknown_support(self):
        ev = theme("lid leaks", "negative", [R[0], R[2]])
        with pytest.raises(ReviewThemeError, match="unknown review"):
            parse_review_theme(ev, {R[0].id: R[0]})  # R[2] not available
        inflated = make_evidence(
            provider="fx",
            kind="review_theme",
            marketplace="US",
            retrieved_at=T,
            payload={**ev.payload, "count": 5},
            subject=ev.subject,
            run_id="r1",
        )
        with pytest.raises(ReviewThemeError, match="count"):
            parse_review_theme(inflated, {r.id: r for r in R})
        wrong_products = make_evidence(
            provider="fx",
            kind="review_theme",
            marketplace="US",
            retrieved_at=T,
            payload={**ev.payload, "products": ["B0C0000009"]},
            subject=ev.subject,
            run_id="r1",
        )
        with pytest.raises(ReviewThemeError, match="products"):
            parse_review_theme(wrong_products, {r.id: r for r in R})


class TestSummary:
    def test_partitions_and_opportunities(self):
        themes = [
            theme("lid leaks", "negative", [R[0], R[1], R[2]], terms=("leak proof", "leak")),
            theme("stays cold", "positive", [R[0], R[2]], terms=("cold",)),
            theme("heavy", "negative", [R[1]]),
            theme("our lid squeaks", "negative", [R[3], R[3]]),  # only our product, count 1
        ]
        report = summarize_review_themes(themes, R, product=PRODUCT, min_count=2)
        assert [i.theme.theme for i in report.complaints] == ["lid leaks"]
        assert [i.theme.theme for i in report.positives] == ["stays cold"]
        assert {i.theme.theme for i in report.other} == {"heavy", "our lid squeaks"}
        complaint, praise = report.opportunities
        assert complaint.basis == "competitor_complaint"
        assert complaint.first_party_support == ("Leak proof lid",)
        assert "only if the product genuinely avoids" in complaint.statement
        assert praise.basis == "competitor_praise" and praise.first_party_support == ()
        assert "If the product offers this" in praise.statement
        # Evidence: the theme record plus every supporting review.
        assert complaint.evidence_ids[0] == themes[0].id
        assert set(complaint.evidence_ids[1:]) == {R[0].id, R[1].id, R[2].id}

    def test_no_claims_without_first_party_support(self):
        product = ProductInput("Acme Bottle", "physical-product")
        report = summarize_review_themes(
            [theme("lid leaks", "negative", [R[0], R[2]])], R, product=product
        )
        [opportunity] = report.opportunities
        assert opportunity.first_party_support == ()
        assert "ProductInput lists" not in opportunity.statement

    def test_own_product_themes_are_not_competitive_opportunities(self):
        both = theme("great value", "positive", [R[3], R[0]])
        report = summarize_review_themes([both], R, product=PRODUCT)
        assert report.positives[0].about_own_product
        assert report.positives[0].competitor_products == ("B0C0000001",)
        own_only = make_evidence(
            provider="fx",
            kind="review_theme",
            marketplace="US",
            retrieved_at=T,
            payload={
                **both.payload,
                "review_evidence_ids": [R[3].id],
                "products": ["B0OWN00001"],
                "count": 1,
            },
            subject="x",
            run_id="r1",
        )
        report = summarize_review_themes([own_only], R, product=PRODUCT, min_count=1)
        assert report.opportunities == ()

    def test_invalid_themes_are_reported_not_used(self):
        ev = theme("lid leaks", "negative", [R[0], R[2]])
        report = summarize_review_themes([ev], R[:1], product=PRODUCT)
        assert report.complaints == () and report.invalid[0][0] == ev.id
        with pytest.raises(ValueError):
            summarize_review_themes([], R, product=PRODUCT, min_count=0)


class TestFixtureProvider:
    def test_resolves_refs_against_supplied_reviews(self):
        fixture = FixtureData.from_dict(
            {
                "provider": "fx",
                "retrieved_at": "2026-10-03T00:00:00+00:00",
                "review_themes": {
                    "extractor": "pre",
                    "extractor_version": "v9",
                    "markets": {
                        "US": [
                            {
                                "theme": "lid leaks",
                                "polarity": "negative",
                                "reviews": ["B0C0000001/0", "B0C0000002/0", "B0NOPE0000/0"],
                            },
                            {"theme": "ghost", "polarity": "positive", "reviews": ["B0NOPE0000/1"]},
                        ]
                    },
                },
            }
        )
        provider = FixtureReviewThemeProvider(fixture)
        assert isinstance(provider, ReviewThemeProvider)
        [ev] = provider.themes(R, marketplace="US", run_id="r1")
        assert ev.payload["count"] == 2  # unresolvable ref dropped; "ghost" omitted
        assert ev.payload["extractor_version"] == "v9"
        assert provider.themes(R, marketplace="UK") == []
