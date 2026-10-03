"""Orchestration behavior of ResearchRun, using small hand-built providers."""

from datetime import datetime

import pytest

from atlas_amazon.evidence import InMemoryEvidenceStore, JsonlEvidenceStore, make_evidence
from atlas_amazon.models import Listing, ProductInput
from atlas_amazon.providers import FixtureData
from atlas_amazon.research import (
    PRIORITY_TASKS,
    ResearchConfig,
    ResearchProviders,
    ResearchRun,
    TaskStatus,
)
from atlas_amazon.research.scenarios import _ROLES
from conftest import T0

FIXTURE = FixtureData.from_dict(
    {
        "provider": "fx",
        "retrieved_at": "2026-10-01T00:00:00+00:00",
        "catalog": {
            "US": {
                "B0C0000001": {"title": "Insulated Water Bottle", "bullets": ["Leak proof lid"]},
                "B0C0000002": {"title": "Steel Water Bottle", "bullets": ["Leak proof cap"]},
            }
        },
        "suggestions": {"US": {"water bottle": ["water bottle with straw"]}},
        "keyword_metrics": {
            "US": {
                "water bottle": {"search_volume": 1000, "competition": 0.9},
                "water bottle with straw": {"search_volume": 300, "competition": 0.4},
                "leak proof": {"search_volume": 100, "competition": 0.2},
            }
        },
        "reviews": {"US": {"B0C0000001": [{"rating": 5, "text": "great"}]}},
    }
)


class Recorder:
    """Wraps a fixture provider and logs every call, in order, into a shared list."""

    def __init__(self, inner, log, store=None):
        self._inner, self._log, self._store = inner, log, store
        self.name = inner.name

    def __getattr__(self, method):
        target = getattr(self._inner, method)

        def call(*args, **kwargs):
            # Snapshot the store size at call time to prove ordering.
            self._log.append((method, len(self._store) if self._store is not None else None))
            return target(*args, **kwargs)

        return call


def providers(log=None, store=None, only=("catalog", "keywords", "suggestions", "reviews")):
    made = {role: _ROLES[role](FIXTURE) for role in only}
    if log is not None:
        made = {role: Recorder(p, log, store) for role, p in made.items()}
    return ResearchProviders(**made)


PRODUCT = ProductInput(
    "Acme Insulated Water Bottle",
    "physical-product",
    competitor_asins=("B0C0000001", "B0C0000002"),
    attributes={"seed_keywords": ["water bottle"]},
)
LISTING = Listing({"title": "Acme Water Bottle", "search_terms": "gym"})


def run(store=None, providers_=None, product=PRODUCT, **kwargs):
    return ResearchRun(
        product=product,
        listing=LISTING,
        recipe_id=product.recipe_id,
        run_id="r1",
        providers=providers_ or providers(),
        store=store if store is not None else InMemoryEvidenceStore(),  # empty stores are falsy
        started_at=T0,
        **kwargs,
    ).execute()


class TestInputs:
    def test_recipe_mismatch(self):
        with pytest.raises(ValueError, match="recipe"):
            ResearchRun(
                product=PRODUCT,
                listing=LISTING,
                recipe_id="book",
                run_id="r",
                providers=providers(),
                store=InMemoryEvidenceStore(),
                started_at=T0,
            )

    def test_naive_start_time_rejected(self):
        with pytest.raises(ValueError, match="timezone"):
            ResearchRun(
                product=PRODUCT,
                listing=LISTING,
                recipe_id="physical-product",
                run_id="r",
                providers=providers(),
                store=InMemoryEvidenceStore(),
                started_at=datetime(2026, 1, 1),
            )

    def test_seed_keywords_validation(self):
        bad = ProductInput("X", "physical-product", attributes={"seed_keywords": "oops"})
        with pytest.raises(ValueError, match="seed_keywords"):
            run(product=bad)

    def test_title_is_seed_when_none_given(self):
        product = ProductInput("Water Bottle", "physical-product")
        result = run(product=product)
        assert result.metadata.seeds == ("water bottle",)
        assert result.metadata.seeds_source == "product title"

    def test_config_validation(self):
        with pytest.raises(ValueError):
            ResearchConfig(top_n=0)


class TestOrchestration:
    def test_priorities_drive_task_order(self):
        result = run()
        assert [t.priority for t in result.tasks] == list(result.metadata.research_priorities)
        assert [t.status for t in result.tasks] == [
            TaskStatus.EXECUTED,  # competitor_titles -> catalog
            TaskStatus.ALREADY_DONE,  # competitor_bullets
            TaskStatus.EXECUTED,  # search_term_demand
            TaskStatus.EXECUTED,  # review_themes
            TaskStatus.ALREADY_DONE,  # category_attributes
        ]

    def test_custom_priority_order_changes_call_order(self, tmp_path):
        (tmp_path / "base.toml").write_text(
            'id = "base"\nversion = "1"\n'
            "[fields.title]\nkind = 'text'\nrequired = true\n"
            "[fields.search_terms]\nkind = 'text'\n"
            "[scoring.keyword]\nrelevance = 0.2\ndemand = 0.2\ncompetition = 0.2\n"
            "intent = 0.2\ncompetitor_coverage = 0.2\n"
            "[scoring.coverage]\ntitle = 1.0\n"
            '[research]\npriorities = ["review_themes", "search_term_demand", '
            '"competitor_titles", "browse_categories"]\n',
            encoding="utf-8",
        )
        log = []
        product = ProductInput(
            PRODUCT.title,
            "base",
            competitor_asins=PRODUCT.competitor_asins,
            attributes=PRODUCT.attributes,
        )
        result = run(product=product, providers_=providers(log), recipe_search_path=tmp_path)
        assert [m for m, _ in log] == [
            "reviews",
            "reviews",
            "suggestions",
            "keyword_metrics",
            "get_items",
        ]
        assert result.tasks[-1].status is TaskStatus.UNSUPPORTED
        # Catalog came last, so metrics were requested without competitor phrases.
        assert "leak proof" in result.evidence.candidates_without_metrics

    def test_evidence_is_stored_before_downstream_calls(self):
        store = InMemoryEvidenceStore()
        log = []
        result = run(store=store, providers_=providers(log, store))
        sizes = dict(log)  # method -> store size when it was (last) called
        # By the time metrics are requested, catalog (2) + suggestion (1) evidence is stored.
        assert sizes["get_items"] == 0
        assert sizes["suggestions"] == 2
        assert sizes["keyword_metrics"] == 3
        assert "leak proof" in [c.keyword for c in result.candidates]
        assert result.derivation("leak proof").scorable  # metrics fetched for competitor phrase

    def test_every_referenced_evidence_id_is_in_the_store(self):
        store = InMemoryEvidenceStore()
        result = run(store=store)
        referenced = set()
        for t in result.tasks:
            referenced.update(t.evidence_ids)
        for c in result.candidates:
            referenced.update(c.evidence_ids)
        for s in result.ranked:
            referenced.update(s.evidence_ids)
        for r in result.recommendations:
            referenced.update(r.evidence_ids)
        for p in result.proposals:
            referenced.update(p.evidence_ids)
        assert referenced
        assert all(i in store for i in referenced)
        assert {e.id for e in store} == set(referenced) | {
            e.id for e in store.query(kind="review_sample")
        }

    def test_missing_providers_are_explicit(self):
        result = run(providers_=providers(only=("catalog",)))
        statuses = {t.priority: t.status for t in result.tasks}
        assert statuses["search_term_demand"] is TaskStatus.NO_PROVIDER
        assert statuses["review_themes"] is TaskStatus.NO_PROVIDER
        assert result.ranked == ()
        assert all(d.missing == ("demand", "competition") for d in result.derivations)
        assert result.backend_plan.proposal is None
        assert result.metadata.providers == {
            "catalog": "fx",
            "keywords": None,
            "suggestions": None,
            "reviews": None,
            "review_themes": None,
            "judgments": None,
            "human_judgments": None,
        }

    def test_no_competitors_is_no_input(self):
        product = ProductInput(
            "Water Bottle", "physical-product", attributes={"seed_keywords": ["water bottle"]}
        )
        result = run(product=product)
        assert result.tasks[0].status is TaskStatus.NO_INPUT
        assert all("competitor_coverage" in d.missing for d in result.derivations)

    def test_provider_returning_foreign_evidence_is_rejected(self):
        class Rogue:
            name = "rogue"

            def get_items(self, asins, *, marketplace, run_id=None):
                return [
                    make_evidence(
                        provider="rogue",
                        kind="catalog_item",
                        marketplace="UK",
                        retrieved_at=T0,
                        payload={},
                        run_id=run_id,
                    )
                ]

        with pytest.raises(ValueError, match="expected 'r1' / 'US'"):
            run(providers_=ResearchProviders(catalog=Rogue()))

    def test_proposals_are_validated(self):
        result = run()
        assert len(result.proposals) == len(result.validations) == 1
        assert result.validations[0].proposal is result.proposals[0]
        assert result.validations[0].valid


class TestReproducibility:
    def test_same_inputs_same_result(self):
        assert run() == run()

    def test_rerun_on_same_store_reuses_evidence(self, tmp_path):
        store = JsonlEvidenceStore(tmp_path / "ev.jsonl")
        first = run(store=store)
        size = len(store)
        second = run(store=JsonlEvidenceStore(tmp_path / "ev.jsonl"))
        assert len(JsonlEvidenceStore(tmp_path / "ev.jsonl")) == size
        assert all(t.new_records == 0 for t in second.tasks)
        assert sum(t.reused_records for t in second.tasks) == sum(
            t.new_records for t in first.tasks
        )
        assert second.ranked == first.ranked
        assert second.proposals == first.proposals
        assert second.metadata.evidence_fingerprint == first.metadata.evidence_fingerprint

    def test_runs_are_isolated_by_run_id(self):
        store = InMemoryEvidenceStore()
        run(store=store)
        other = ResearchRun(
            product=PRODUCT,
            listing=LISTING,
            recipe_id="physical-product",
            run_id="r2",
            providers=providers(),
            store=store,
            started_at=T0,
        ).execute()
        assert len(store.query(run_id="r1")) == len(store.query(run_id="r2"))
        assert other.evidence.total == len(store.query(run_id="r2"))


def test_priority_registry_covers_known_task_names():
    assert set(PRIORITY_TASKS.values()) == {
        "competitor_catalog",
        "search_demand",
        "competitor_reviews",
    }
