"""Golden example reports in docs/examples/ must match a fresh offline run.

Regenerate after an intentional change:

    ATLAS_REGEN_EXAMPLES=1 pytest tests/test_examples.py
"""

import os
from pathlib import Path

import pytest

from atlas_amazon.report import render_markdown
from atlas_amazon.research import load_scenario

ROOT = Path(__file__).parent.parent
SCENARIOS = ROOT / "tests" / "fixtures" / "scenarios"
EXAMPLES = ROOT / "docs" / "examples"
NAMES = ["book_cozy_mystery", "physical_water_bottle"]


@pytest.mark.parametrize("name", NAMES)
def test_example_report_is_current(name):
    rendered = render_markdown(load_scenario(SCENARIOS / f"{name}.json").run())
    path = EXAMPLES / f"{name}.md"
    if os.environ.get("ATLAS_REGEN_EXAMPLES") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")
    assert path.read_text(encoding="utf-8") == rendered, (
        f"{path} is stale; regenerate with ATLAS_REGEN_EXAMPLES=1 pytest tests/test_examples.py"
    )
