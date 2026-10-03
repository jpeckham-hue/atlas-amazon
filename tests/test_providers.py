import pytest

from atlas_amazon.evidence import JsonlEvidenceStore
from atlas_amazon.models import Evidence, EvidenceKind
from atlas_amazon.providers import (
    CatalogProvider,
    FixtureCatalogProvider,
    FixtureData,
    FixtureError,
    FixtureKeywordDataProvider,
    FixtureReviewProvider,
    FixtureSuggestionProvider,
    KeywordDataProvider,
    ReviewProvider,
    SuggestionProvider,
)


@pytest.fixture
def fixture(sample_fixture_path):
    return FixtureData.load(sample_fixture_path)


def test_fakes_satisfy_their_protocols(fixture):
    assert isinstance(FixtureCatalogProvider(fixture), CatalogProvider)
    assert isinstance(FixtureKeywordDataProvider(fixture), KeywordDataProvider)
    assert isinstance(FixtureSuggestionProvider(fixture), SuggestionProvider)
    assert isinstance(FixtureReviewProvider(fixture), ReviewProvider)


class TestCatalog:
    def test_returns_evidence_for_known_asins_only(self, fixture):
        provider = FixtureCatalogProvider(fixture)
        result = provider.get_items(
            ["B0COMP0001", "B0UNKNOWN1", "B0COMP0002", "B0COMP0001"], marketplace="US", run_id="r1"
        )
        assert [e.subject for e in result] == ["B0COMP0001", "B0COMP0002"]
        first = result[0]
        assert isinstance(first, Evidence)
        assert first.kind == EvidenceKind.CATALOG_ITEM
        assert first.provider == "fixture"
        assert first.marketplace == "US"
        assert first.run_id == "r1"
        assert first.retrieved_at.isoformat() == "2026-10-01T12:00:00+00:00"
        assert first.source_url == "fixture://sample_us.json#catalog/US/B0COMP0001"
        assert first.payload["bullets"] == ("Leak proof lid", "Keeps drinks cold for 24 hours")

    def test_other_marketplace_has_no_data(self, fixture):
        assert FixtureCatalogProvider(fixture).get_items(["B0COMP0001"], marketplace="UK") == []

    def test_validates_inputs(self, fixture):
        provider = FixtureCatalogProvider(fixture)
        with pytest.raises(ValueError, match="invalid ASIN"):
            provider.get_items(["bad"], marketplace="US")
        with pytest.raises(ValueError, match="marketplace"):
            provider.get_items(["B0COMP0001"], marketplace="")

    def test_deterministic(self, fixture):
        a = FixtureCatalogProvider(fixture).get_items(["B0COMP0001"], marketplace="US")
        b = FixtureCatalogProvider(fixture).get_items(["B0COMP0001"], marketplace="US")
        assert a == b
        c = FixtureCatalogProvider(fixture).get_items(["B0COMP0001"], marketplace="US", run_id="x")
        assert a[0].id != c[0].id  # run-scoped identity


class TestKeywordMetrics:
    def test_normalized_lookup_and_payload(self, fixture):
        provider = FixtureKeywordDataProvider(fixture)
        result = provider.keyword_metrics(
            ["Water Bottle!", "water  bottle", "unknown kw", "GYM bottle"], marketplace="US"
        )
        assert [e.subject for e in result] == ["water bottle", "gym bottle"]
        assert result[0].kind == "keyword_metric"
        assert dict(result[0].payload) == {
            "keyword": "water bottle",
            "search_volume": 120000,
            "competition": 0.82,
        }


class TestSuggestions:
    def test_seed_lookup(self, fixture):
        provider = FixtureSuggestionProvider(fixture)
        [ev] = provider.suggestions("Water Bot", marketplace="US", run_id="r1")
        assert ev.kind == "autocomplete_suggestion"
        assert ev.subject == "water bot"
        assert ev.payload["suggestions"][0] == "water bottle"
        assert provider.suggestions("nothing", marketplace="US") == []
        assert provider.suggestions("   ", marketplace="US") == []


class TestReviews:
    def test_one_evidence_per_review_with_limit(self, fixture):
        provider = FixtureReviewProvider(fixture)
        all_reviews = provider.reviews("B0COMP0001", marketplace="US")
        assert [e.payload["index"] for e in all_reviews] == [0, 1, 2]
        assert all(e.kind == "review_sample" for e in all_reviews)
        assert len({e.id for e in all_reviews}) == 3
        assert all_reviews[1].payload["rating"] == 2
        assert all_reviews[2].source_url.endswith("#reviews/US/B0COMP0001/2")
        assert len(provider.reviews("B0COMP0001", marketplace="US", limit=2)) == 2
        assert provider.reviews("B0COMP0002", marketplace="US") == []

    def test_validates_inputs(self, fixture):
        provider = FixtureReviewProvider(fixture)
        with pytest.raises(ValueError):
            provider.reviews("nope", marketplace="US")
        with pytest.raises(ValueError):
            provider.reviews("B0COMP0001", marketplace="US", limit=-1)


def test_provider_evidence_round_trips_through_jsonl_store(fixture, tmp_path):
    store = JsonlEvidenceStore(tmp_path / "ev.jsonl")
    run = "run-42"
    store.append_many(
        FixtureCatalogProvider(fixture).get_items(
            ["B0COMP0001", "B0COMP0002"], marketplace="US", run_id=run
        )
        + FixtureKeywordDataProvider(fixture).keyword_metrics(
            ["water bottle"], marketplace="US", run_id=run
        )
        + FixtureSuggestionProvider(fixture).suggestions("water bot", marketplace="US", run_id=run)
        + FixtureReviewProvider(fixture).reviews("B0COMP0001", marketplace="US", run_id=run)
    )
    reopened = JsonlEvidenceStore(tmp_path / "ev.jsonl")
    assert len(reopened.query(run_id=run)) == 7
    assert len(reopened.query(run_id=run, kind="review_sample")) == 3
    assert list(reopened) == list(store)


FIXTURE_BASE = {"provider": "f", "retrieved_at": "2026-10-01T00:00:00+00:00"}


class TestFixtureValidation:
    @pytest.mark.parametrize(
        ("data", "match"),
        [
            ({**FIXTURE_BASE, "surprise": {}}, "unknown fixture keys"),
            ({**FIXTURE_BASE, "provider": ""}, "provider"),
            ({**FIXTURE_BASE, "retrieved_at": "yesterday"}, "ISO 8601"),
            ({**FIXTURE_BASE, "retrieved_at": "2026-10-01T00:00:00"}, "UTC offset"),
            ({**FIXTURE_BASE, "catalog": {"US": []}}, "marketplace -> object"),
        ],
    )
    def test_invalid_fixtures(self, data, match):
        with pytest.raises(FixtureError, match=match):
            FixtureData.from_dict(data)

    def test_colliding_normalized_keys(self):
        data = {**FIXTURE_BASE, "keyword_metrics": {"US": {"Mug": {}, "mug": {}}}}
        provider = FixtureKeywordDataProvider(FixtureData.from_dict(data))
        with pytest.raises(FixtureError, match="collide"):
            provider.keyword_metrics(["mug"], marketplace="US")

    def test_malformed_entries(self):
        data = {
            **FIXTURE_BASE,
            "catalog": {"US": {"B0COMP0001": "not an object"}},
            "reviews": {"US": {"B0COMP0001": {"not": "a list"}}},
            "suggestions": {"US": {"seed": [1, 2]}},
        }
        fixture = FixtureData.from_dict(data)
        with pytest.raises(FixtureError):
            FixtureCatalogProvider(fixture).get_items(["B0COMP0001"], marketplace="US")
        with pytest.raises(FixtureError):
            FixtureReviewProvider(fixture).reviews("B0COMP0001", marketplace="US")
        with pytest.raises(FixtureError):
            FixtureSuggestionProvider(fixture).suggestions("seed", marketplace="US")

    def test_invalid_json_file(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{", encoding="utf-8")
        with pytest.raises(FixtureError, match="invalid JSON"):
            FixtureData.load(path)
