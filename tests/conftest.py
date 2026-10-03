from datetime import UTC, datetime
from pathlib import Path

import pytest

from atlas_amazon.evidence import make_evidence

FIXTURES = Path(__file__).parent / "fixtures"
T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def sample_evidence(n: int = 0, **overrides):
    """A small valid Evidence record; vary `n` for distinct IDs."""
    fields = {
        "provider": "test",
        "kind": "keyword_metric",
        "marketplace": "US",
        "retrieved_at": T0,
        "payload": {"keyword": f"kw{n}", "search_volume": 100 + n},
        "subject": f"kw{n}",
        "run_id": "run-1",
        "source_url": f"https://example.test/kw{n}",
    }
    fields.update(overrides)
    return make_evidence(**fields)


@pytest.fixture
def sample_fixture_path():
    return FIXTURES / "sample_us.json"
