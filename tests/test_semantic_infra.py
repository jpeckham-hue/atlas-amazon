"""Prompts, records, secrets, cache, pricing and usage limits."""

import json
from dataclasses import replace

import pytest

from atlas_amazon.semantic import (
    BudgetExceeded,
    CacheKey,
    ModelPrice,
    PricingTable,
    SecretLeakError,
    SemanticBudget,
    SemanticCache,
    UsageLedger,
    ensure_no_secrets,
    find_secrets,
    load_template,
)
from atlas_amazon.semantic.prompts import (
    TEMPLATE_NAMES,
    PromptError,
    historical_templates,
    load_lock,
)
from atlas_amazon.semantic.records import ChecksummedJsonl, RecordFileError
from atlas_amazon.semantic.usage import UsageRecord, estimate_tokens


class TestPrompts:
    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_templates_match_lock_file(self, name):
        """Editing a template or schema without bumping its version fails here."""
        template = load_template(name)
        lock = load_lock()
        assert template.version in lock, f"add {template.version} to prompts/lock.json"
        assert lock[template.version] == template.fingerprint, (
            f"{name}.toml changed without a version bump: bump `version` and update lock.json"
        )

    def test_historical_versions_stay_locked_and_loadable(self):
        lock = load_lock()
        history = historical_templates()
        assert history  # bumped templates keep their previous version
        for template in history:
            assert lock[template.version] == template.fingerprint, (
                f"history/{template.version}.toml must not change"
            )
            assert load_template(template.name, template.version) == template
        with pytest.raises(PromptError):
            load_template("judgment_batch", "judgment_batch-v0")

    def test_lock_has_no_orphans(self):
        versions = {load_template(n).version for n in TEMPLATE_NAMES}
        versions |= {t.version for t in historical_templates()}
        assert set(load_lock()) == versions

    def test_fingerprint_covers_text_and_schema(self):
        t = load_template("relevance")
        assert replace(t, user=t.user + " ").fingerprint != t.fingerprint
        assert replace(t, schema={**t.schema, "x": 1}).fingerprint != t.fingerprint
        assert replace(t, max_tokens=1).fingerprint != t.fingerprint

    def test_render_inserts_sorted_json_once(self):
        rendered = load_template("intent").render_user({"keyword": "mug", "context": {"b": 1}})
        assert "<input>" in rendered and '"keyword": "mug"' in rendered
        assert "{input_json}" not in rendered

    def test_schemas_are_strict_objects(self):
        for name in TEMPLATE_NAMES:
            schema = load_template(name).schema
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) == set(schema["properties"])

    def test_unknown_template(self):
        with pytest.raises(PromptError):
            load_template("nope")


class TestRecordsAndSecrets:
    def test_append_only_checksummed(self, tmp_path):
        f = ChecksummedJsonl(tmp_path / "r.jsonl")
        f.append([{"a": 1}, {"b": [1, 2]}])
        f.append([{"c": "é"}])
        assert f.read() == [{"a": 1}, {"b": [1, 2]}, {"c": "é"}]
        text = (tmp_path / "r.jsonl").read_text(encoding="utf-8")
        (tmp_path / "r.jsonl").write_text(text.replace('"a":1', '"a":2'), encoding="utf-8")
        with pytest.raises(RecordFileError, match="checksum"):
            f.read()

    def test_truncated(self, tmp_path):
        (tmp_path / "r.jsonl").write_text('{"v":1}', encoding="utf-8")
        with pytest.raises(RecordFileError, match="truncated"):
            ChecksummedJsonl(tmp_path / "r.jsonl").read()

    @pytest.mark.parametrize(
        "value",
        [
            # Fake credentials are assembled at runtime so the repository itself never
            # contains a credential-shaped string (see test_repository_has_no_secrets).
            {"key": "sk-" + "ant-api03-" + "abcdefghijklmnop"},
            {"headers": {"Authorization": "Bea" + "rer " + "abcdefghijklmnopqrstuvwxyz0123"}},
            {"api_key": "anything"},
            ["x", {"x-api-key": "k"}],
            {"text": "api" + '_key="' + "abcdefghijklmnopqrstu" + '"'},
        ],
    )
    def test_secret_detection(self, value):
        assert find_secrets(value)
        with pytest.raises(SecretLeakError):
            ensure_no_secrets(value, "test")

    def test_ordinary_content_passes(self):
        ensure_no_secrets(
            {"model": "claude-opus-5-5", "text": "insulated water bottle", "max_tokens": 4096},
            "test",
        )

    def test_records_refuse_secrets(self, tmp_path):
        with pytest.raises(SecretLeakError):
            ChecksummedJsonl(tmp_path / "r.jsonl").append([{"t": "sk-" + "ant-abcdefghijk12345"}])
        assert not (tmp_path / "r.jsonl").exists()


class TestCache:
    KEY = CacheKey("relevance", "sha256:abc", "anthropic", "claude-opus-5-5", "relevance-v1")

    def test_hit_requires_every_key_part_and_fingerprint(self, tmp_path):
        cache = SemanticCache(tmp_path / "c.jsonl")
        cache.put(self.KEY, "fp1", {"value": 1})
        assert cache.lookup(self.KEY, "fp1").entry == {"value": 1}
        for change in (
            {"kind": "intent"},
            {"input_hash": "sha256:other"},
            {"provider": "other"},
            {"model": "claude-sonnet-5-5"},
            {"prompt_version": "relevance-v2"},
        ):
            assert cache.lookup(replace(self.KEY, **change), "fp1").reason == "absent"
        stale = cache.lookup(self.KEY, "fp2")
        assert stale.entry is None and stale.reason == "stale_prompt"

    def test_persists_and_prefers_newest(self, tmp_path):
        cache = SemanticCache(tmp_path / "c.jsonl")
        cache.put(self.KEY, "fp1", {"v": 1})
        cache.put(self.KEY, "fp1", {"v": 2})
        reopened = SemanticCache(tmp_path / "c.jsonl")
        assert reopened.lookup(self.KEY, "fp1").entry == {"v": 2}
        assert len(reopened) == 2


REQ = {"model": "claude-opus-5-5", "max_tokens": 1000, "messages": [{"content": "x" * 400}]}


class TestUsageLimits:
    REQ = REQ

    def ledger(self, **budget):
        return UsageLedger(budget=SemanticBudget(**budget))

    def live(self, ledger, cost=0.01, run="r1"):
        ledger.record(
            UsageRecord(
                run,
                "anthropic",
                "claude-opus-5-5",
                "judgment:relevance",
                "relevance-v1",
                "live",
                "ok",
                100,
                50,
                0,
                0,
                cost,
            )
        )

    def test_call_limit_refuses_before_next_call(self):
        ledger = self.ledger(max_live_calls=2)
        ledger.authorize(run_id="r1", model="claude-opus-5-5", request=self.REQ)
        self.live(ledger)
        self.live(ledger)
        with pytest.raises(BudgetExceeded, match="max_live_calls=2"):
            ledger.authorize(run_id="r1", model="claude-opus-5-5", request=self.REQ)
        ledger.authorize(run_id="r2", model="claude-opus-5-5", request=self.REQ)  # per run
        assert ledger.summary("r1").halts == ("max_live_calls=2 reached",)

    def test_cost_limit_uses_worst_case_next_call(self):
        ledger = self.ledger(max_cost_usd=0.03)
        worst = ModelPrice(4.0, 20.0).cost(estimate_tokens(self.REQ), 1000)  # ~0.0205
        ledger.authorize(run_id="r1", model="claude-opus-5-5", request=self.REQ)
        self.live(ledger, cost=0.01)
        assert 0.01 + worst > 0.03
        with pytest.raises(BudgetExceeded, match="max_cost_usd"):
            ledger.authorize(run_id="r1", model="claude-opus-5-5", request=self.REQ)

    def test_unpriced_model_cannot_be_bounded(self):
        ledger = self.ledger(max_cost_usd=1.0)
        with pytest.raises(BudgetExceeded, match="cannot bound cost"):
            ledger.authorize(run_id="r1", model="mystery-model", request=self.REQ)
        self.ledger().authorize(run_id="r1", model="mystery-model", request=self.REQ)  # no limit

    def test_zero_limits_block_everything(self):
        with pytest.raises(BudgetExceeded):
            self.ledger(max_live_calls=0).authorize(run_id="r", model="m", request=self.REQ)

    def test_summary_groups_and_costs(self):
        ledger = UsageLedger(pricing=PricingTable())
        self.live(ledger, cost=0.01)
        self.live(ledger, cost=0.02)
        ledger.record(
            UsageRecord(
                "r1",
                "anthropic",
                "claude-opus-5-5",
                "judgment:intent",
                "intent-v1",
                "cache",
                "ok",
                estimated_cost_usd=0.0,
            )
        )
        ledger.record(
            UsageRecord(
                "r1",
                "anthropic",
                "claude-opus-5-5",
                "judgment:intent",
                "intent-v1",
                "live",
                "malformed",
                10,
                5,
                0,
                0,
                0.001,
            )
        )
        s = ledger.summary("r1")
        [g] = s.groups
        assert (g.requests, g.live_calls, g.cache_hits, g.cache_misses) == (4, 3, 1, 3)
        assert g.failures == {"malformed": 1}
        assert g.estimated_cost_usd == pytest.approx(0.031)
        assert s.estimated_cost_usd == pytest.approx(0.031)
        assert ledger.cost_of("claude-opus-5-5", {"input_tokens": 1_000_000}) == 4.0
        assert ledger.cost_of("unknown", {"input_tokens": 1}) is None

    def test_budget_validation(self):
        with pytest.raises(ValueError):
            SemanticBudget(max_live_calls=-1)

    def test_estimate_is_rough_and_positive(self):
        assert estimate_tokens({}) >= 1
        assert estimate_tokens({"t": "x" * 4000}) > 900
        json.dumps(self.REQ)


def test_repository_has_no_secrets():
    """No committed text file (code, fixtures, recordings, docs) contains a credential."""
    from pathlib import Path

    root = Path(__file__).parent.parent
    suffixes = {".py", ".md", ".toml", ".json", ".jsonl", ".txt", ".cfg", ".ini", ".yml", ".yaml"}
    scanned = 0
    for path in root.rglob("*"):
        parts = set(path.parts)
        if path.suffix not in suffixes or parts & {".venv", ".git", "__pycache__", "var"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        assert not find_secrets(text), f"possible credential in {path.relative_to(root)}"
        scanned += 1
    assert scanned > 50
