from datetime import UTC, datetime, timedelta, timezone

import pytest

from atlas_amazon.evidence import (
    CorruptEvidenceError,
    DuplicateEvidenceError,
    EvidenceNotFoundError,
    EvidenceStore,
    InMemoryEvidenceStore,
    JsonlEvidenceStore,
    decode_record,
    encode_record,
    evidence_id_for,
    make_evidence,
)
from atlas_amazon.models import Evidence
from conftest import T0, sample_evidence


@pytest.fixture(params=["memory", "jsonl"])
def store(request, tmp_path):
    if request.param == "memory":
        return InMemoryEvidenceStore()
    return JsonlEvidenceStore(tmp_path / "evidence.jsonl")


# ---------------------------------------------------------------------------
# Identity


class TestIdentity:
    def test_id_is_deterministic_and_ignores_retrieval_time(self):
        a = sample_evidence(1)
        b = sample_evidence(1, retrieved_at=T0 + timedelta(days=3))
        assert a.id == b.id
        assert a.id.startswith("ev_")

    @pytest.mark.parametrize(
        "change",
        [
            {"run_id": "run-2"},
            {"payload": {"keyword": "kw1", "search_volume": 999}},
            {"provider": "other"},
            {"marketplace": "UK"},
            {"subject": "other"},
            {"kind": "catalog_item"},
        ],
    )
    def test_identity_fields_change_the_id(self, change):
        assert sample_evidence(1).id != sample_evidence(1, **change).id

    def test_payload_key_order_does_not_matter(self):
        common = dict(provider="p", kind="k", marketplace="US", subject=None, run_id=None)
        assert evidence_id_for(payload={"a": 1, "b": 2}, **common) == evidence_id_for(
            payload={"b": 2, "a": 1}, **common
        )

    def test_enum_kind_is_stored_as_plain_string(self):
        from atlas_amazon.models import EvidenceKind

        ev = make_evidence(
            provider="p",
            kind=EvidenceKind.REVIEW_SAMPLE,
            marketplace="US",
            retrieved_at=T0,
            payload={},
        )
        assert type(ev.kind) is str


# ---------------------------------------------------------------------------
# Serialization


class TestSerialization:
    def test_round_trip_preserves_everything(self):
        tz = timezone(timedelta(hours=-7))
        ev = sample_evidence(
            5,
            retrieved_at=datetime(2026, 10, 1, 5, 4, 3, 123456, tzinfo=tz),
            payload={"text": "Ça marche — 日本", "nested": {"list": [1, 2.5, None, True]}},
        )
        back = decode_record(encode_record(ev))
        assert back == ev
        assert back.retrieved_at.utcoffset() == timedelta(hours=-7)
        assert back.retrieved_at.microsecond == 123456
        assert back.payload["nested"]["list"] == (1, 2.5, None, True)

    def test_record_is_one_lf_terminated_line(self):
        line = encode_record(sample_evidence(1, payload={"text": "a\nb"}))
        assert line.endswith("\n")
        assert line.count("\n") == 1

    @pytest.mark.parametrize(
        ("mutate", "match"),
        [
            (lambda s: s[:-5] + "\n", "invalid JSON"),
            (lambda s: s.replace('"search_volume":101', '"search_volume":999'), "checksum"),
            (lambda s: s.replace('"v":1', '"v":2'), "version"),
            (lambda s: '{"v":1}\n', "exactly"),
            (lambda s: "[]\n", "exactly"),
        ],
    )
    def test_decode_detects_damage(self, mutate, match):
        line = encode_record(sample_evidence(1))
        with pytest.raises(ValueError, match=match):
            decode_record(mutate(line))


# ---------------------------------------------------------------------------
# Store contract (both implementations)


class TestStoreContract:
    def test_satisfies_protocol(self, store):
        assert isinstance(store, EvidenceStore)

    def test_append_get_contains_len_iter(self, store):
        a, b = sample_evidence(1), sample_evidence(2)
        store.append(a)
        store.append(b)
        assert store.get(a.id) == a
        assert a.id in store
        assert "ev_missing" not in store
        assert len(store) == 2
        assert list(store) == [a, b]

    def test_get_missing_raises(self, store):
        with pytest.raises(EvidenceNotFoundError) as info:
            store.get("ev_missing")
        assert isinstance(info.value, KeyError)
        assert "ev_missing" in str(info.value)

    def test_duplicate_id_rejected(self, store):
        ev = sample_evidence(1)
        store.append(ev)
        with pytest.raises(DuplicateEvidenceError) as info:
            store.append(sample_evidence(1, retrieved_at=T0 + timedelta(hours=1)))
        assert info.value.ids == (ev.id,)
        assert len(store) == 1
        assert store.get(ev.id).retrieved_at == T0  # original untouched

    def test_append_many_is_all_or_nothing(self, store):
        existing = sample_evidence(1)
        store.append(existing)
        with pytest.raises(DuplicateEvidenceError):
            store.append_many([sample_evidence(2), existing])
        with pytest.raises(DuplicateEvidenceError):
            store.append_many([sample_evidence(3), sample_evidence(3)])
        with pytest.raises(TypeError):
            store.append_many([sample_evidence(4), {"id": "x"}])
        assert len(store) == 1

    def test_query_filters(self, store):
        a = sample_evidence(1, run_id="r1", provider="p1", kind="k1", marketplace="US")
        b = sample_evidence(2, run_id="r1", provider="p2", kind="k2", marketplace="UK")
        c = sample_evidence(3, run_id="r2", provider="p1", kind="k1", marketplace="US")
        d = sample_evidence(4, run_id=None, subject=None)
        store.append_many([a, b, c, d])
        assert store.query() == [a, b, c, d]
        assert store.query(run_id="r1") == [a, b]
        assert store.query(provider="p1") == [a, c]
        assert store.query(kind="k2") == [b]
        assert store.query(marketplace="US", run_id="r2") == [c]
        assert store.query(subject="kw2") == [b]
        assert store.query(run_id="nope") == []

    def test_records_are_immutable(self, store):
        ev = sample_evidence(1, payload={"items": [1, 2]})
        store.append(ev)
        stored = store.get(ev.id)
        with pytest.raises(AttributeError):
            stored.payload = {}  # type: ignore[misc]
        with pytest.raises(TypeError):
            stored.payload["items"] = ()  # type: ignore[index]
        assert not hasattr(store, "update") and not hasattr(store, "delete")


# ---------------------------------------------------------------------------
# JSONL specifics


class TestJsonlStore:
    def test_persists_and_reloads(self, tmp_path):
        path = tmp_path / "ev.jsonl"
        first = JsonlEvidenceStore(path)
        records = [sample_evidence(i) for i in range(5)]
        first.append_many(records[:3])
        first.append_many(records[3:])
        reopened = JsonlEvidenceStore(path)
        assert list(reopened) == records
        assert reopened.query(subject="kw4") == [records[4]]

    def test_file_is_append_only(self, tmp_path):
        path = tmp_path / "ev.jsonl"
        store = JsonlEvidenceStore(path)
        store.append(sample_evidence(1))
        before = path.read_bytes()
        store.append(sample_evidence(2))
        after = path.read_bytes()
        assert after.startswith(before)
        assert b"\r\n" not in after
        assert after.count(b"\n") == 2

    def test_duplicate_across_reopen_rejected(self, tmp_path):
        path = tmp_path / "ev.jsonl"
        JsonlEvidenceStore(path).append(sample_evidence(1))
        with pytest.raises(DuplicateEvidenceError):
            JsonlEvidenceStore(path).append(sample_evidence(1))
        assert path.read_text(encoding="utf-8").count("\n") == 1

    def test_empty_batch_writes_nothing(self, tmp_path):
        path = tmp_path / "sub" / "ev.jsonl"
        JsonlEvidenceStore(path).append_many([])
        assert not path.exists()

    def test_creates_parent_directories(self, tmp_path):
        path = tmp_path / "a" / "b" / "ev.jsonl"
        JsonlEvidenceStore(path).append(sample_evidence(1))
        assert path.exists()

    def _write_lines(self, path, lines):
        path.write_text("".join(lines), encoding="utf-8", newline="\n")

    @pytest.mark.parametrize(
        ("damage", "line", "reason"),
        [
            (lambda ls: [ls[0], ls[1][:-1]], 2, "truncated"),
            (lambda ls: [ls[0], "\n", ls[1]], 2, "blank line"),
            (lambda ls: [ls[0], "{not json}\n"], 2, "invalid JSON"),
            (lambda ls: [ls[0].replace("kw0", "kwX"), ls[1]], 1, "checksum"),
            (lambda ls: [ls[0], ls[1], ls[0]], 3, "duplicate evidence ID"),
        ],
    )
    def test_corruption_detected_on_open(self, tmp_path, damage, line, reason):
        path = tmp_path / "ev.jsonl"
        lines = [encode_record(sample_evidence(i)) for i in range(2)]
        self._write_lines(path, damage(lines))
        with pytest.raises(CorruptEvidenceError) as info:
            JsonlEvidenceStore(path)
        assert info.value.line == line
        assert reason in info.value.reason

    def test_verify_detects_external_changes(self, tmp_path):
        path = tmp_path / "ev.jsonl"
        store = JsonlEvidenceStore(path)
        store.append_many([sample_evidence(1), sample_evidence(2)])
        store.verify()  # clean

        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encode_record(sample_evidence(3)))
        with pytest.raises(CorruptEvidenceError, match="3 records, store has 2"):
            store.verify()

    def test_verify_detects_replaced_record(self, tmp_path):
        path = tmp_path / "ev.jsonl"
        store = JsonlEvidenceStore(path)
        store.append_many([sample_evidence(1), sample_evidence(2)])
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        # A well-formed record (valid checksum) swapped in by another process.
        lines[1] = encode_record(sample_evidence(9))
        path.write_text("".join(lines), encoding="utf-8", newline="\n")
        with pytest.raises(CorruptEvidenceError, match="differs"):
            store.verify()

    def test_verify_detects_deleted_file(self, tmp_path):
        path = tmp_path / "ev.jsonl"
        store = JsonlEvidenceStore(path)
        store.append(sample_evidence(1))
        path.unlink()
        with pytest.raises(CorruptEvidenceError):
            store.verify()


def test_evidence_model_validation():
    with pytest.raises(ValueError, match="subject"):
        Evidence("e", "k", "p", "US", T0, subject="")
    with pytest.raises(TypeError):
        Evidence("e", "k", "p", "US", T0, payload={"bad": {1, 2}})
    with pytest.raises(TypeError):
        Evidence("e", "k", "p", "US", T0, payload=[1, 2])  # type: ignore[arg-type]
    ev = Evidence("e", "k", "p", "US", datetime(2026, 1, 1, tzinfo=UTC), payload={"a": [1]})
    assert ev.payload["a"] == (1,)
