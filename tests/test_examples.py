"""Golden example reports in docs/examples/ must match a fresh offline run.

Regenerate after an intentional change:

    ATLAS_REGEN_EXAMPLES=1 pytest tests/test_examples.py

The evaluation and replay examples use the SYNTHETIC recordings in
tests/fixtures/recordings/ (scripted responses, not model output) and say so.
"""

import os
from pathlib import Path

import pytest

from atlas_amazon.report import render_markdown
from atlas_amazon.research import load_scenario
from atlas_amazon.semantic import evaluate_judgments, render_evaluation_markdown
from test_semantic_replay import replay_scenario

ROOT = Path(__file__).parent.parent
SCENARIOS = ROOT / "tests" / "fixtures" / "scenarios"
EXAMPLES = ROOT / "docs" / "examples"
NAMES = ["book_cozy_mystery", "physical_water_bottle"]
SYNTHETIC_NOTE = (
    '> **Synthetic example.** The "model" judgments here are replayed from a scripted '
    "recording (`synthetic-scripted-v1`), not from a live model. They exercise the live code "
    "path offline. Real agreement figures need a recording made with a live model.\n\n"
)


def check(path: Path, rendered: str) -> None:
    if os.environ.get("ATLAS_REGEN_EXAMPLES") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")
    assert path.read_text(encoding="utf-8") == rendered, (
        f"{path} is stale; regenerate with ATLAS_REGEN_EXAMPLES=1 pytest tests/test_examples.py"
    )


@pytest.mark.parametrize("name", NAMES)
def test_example_report_is_current(name):
    check(EXAMPLES / f"{name}.md", render_markdown(load_scenario(SCENARIOS / f"{name}.json").run()))


@pytest.mark.parametrize("name", NAMES)
def test_evaluation_example_is_current(name):
    reference = load_scenario(SCENARIOS / f"{name}.json").run()
    report = evaluate_judgments(
        replay_scenario(name).judgments,
        reference.judgments,
        candidate_label="replayed model",
        reference_label="fixture judgments",
    )
    check(EXAMPLES / f"evaluation_{name}.md", SYNTHETIC_NOTE + render_evaluation_markdown(report))


def test_replayed_report_example_is_current():
    check(
        EXAMPLES / "replayed_physical_water_bottle.md",
        SYNTHETIC_NOTE + render_markdown(replay_scenario("physical_water_bottle")),
    )
