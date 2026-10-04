"""Old (v0.4b) vs new (v0.5) semantic architecture on the two example scenarios.

The golden report docs/benchmarks/semantic_cost_v0.5.md must match a fresh
offline computation. Regenerate after an intentional change:

    ATLAS_REGEN_EXAMPLES=1 pytest tests/test_benchmark.py
"""

import pytest

from atlas_amazon.semantic.benchmark import benchmark_scenario, render_benchmark_markdown
from semantic_helpers import RECORDINGS, SCENARIOS
from test_examples import ROOT, check

NAMES = ["book_cozy_mystery", "physical_water_bottle"]


@pytest.fixture(scope="module")
def rows():
    return [
        benchmark_scenario(
            name,
            scenarios=SCENARIOS,
            recordings=RECORDINGS,
            v04b_recordings=RECORDINGS / "v04b",
        )
        for name in NAMES
    ]


def test_benchmark_report_is_current(rows):
    check(ROOT / "docs" / "benchmarks" / "semantic_cost_v0.5.md", render_benchmark_markdown(rows))


@pytest.mark.parametrize("index", range(len(NAMES)))
def test_same_judgments_far_fewer_calls_and_a_bounded_worst_case(rows, index):
    r = rows[index]
    # v0.4b made one call per judgment plus one review-theme call.
    assert r.old.calls == r.judgments_requested + 1
    assert r.new.calls <= 8 and r.plan.worst_case_calls <= 8
    assert r.plan.expected_cost_usd < r.old.estimated_cost_usd / 3
    assert r.plan.worst_case_cost_usd < r.old.worst_case_cost_usd / 25
    assert r.plan.expected_cost_usd < 0.05  # low single-digit cents per product
    assert r.downstream_identical, r.differences
    answered = r.human + r.deterministic + r.skipped + r.model_judgments
    assert answered == r.judgments_requested
