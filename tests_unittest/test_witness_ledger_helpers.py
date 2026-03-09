"""Tests for pure helpers in workspace/scripts/witness_ledger.py.

Covers:
- canonicalize(obj) — sorted compact JSON bytes
- _utc_now() — ISO UTC timestamp ending in 'Z'
- _payload_hash(seq, timestamp_utc, prev_hash, record) — SHA-256 hex
- _last_commit(path) — last valid JSON dict from JSONL or None
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "witness_ledger.py"

_spec = _ilu.spec_from_file_location("witness_ledger_real", str(SCRIPT_PATH))
_mod = _ilu.module_from_spec(_spec)
sys.modules["witness_ledger_real"] = _mod
_spec.loader.exec_module(_mod)

canonicalize = _mod.canonicalize
_utc_now = _mod._utc_now
_payload_hash = _mod._payload_hash
_last_commit = _mod._last_commit


# ---------------------------------------------------------------------------
# canonicalize
# ---------------------------------------------------------------------------


class TestCanonicalize(unittest.TestCase):
    """Tests for canonicalize() — sorted compact JSON bytes."""

    def test_returns_bytes(self):
        self.assertIsInstance(canonicalize({}), bytes)

    def test_empty_dict(self):
        self.assertEqual(canonicalize({}), b"{}")

    def test_keys_sorted(self):
        result = canonicalize({"z": 2, "a": 1})
        idx_a = result.find(b'"a"')
        idx_z = result.find(b'"z"')
        self.assertLess(idx_a, idx_z)

    def test_no_spaces(self):
        result = canonicalize({"x": 1})
        self.assertNotIn(b" ", result)

    def test_deterministic(self):
        obj = {"b": 2, "a": 1}
        self.assertEqual(canonicalize(obj), canonicalize(obj))

    def test_list_value(self):
        result = canonicalize({"items": [1, 2, 3]})
        self.assertIn(b"[1,2,3]", result)

    def test_nested_dict(self):
        result = canonicalize({"outer": {"inner": 42}})
        self.assertIn(b'"inner":42', result)


# ---------------------------------------------------------------------------
# _utc_now
# ---------------------------------------------------------------------------


class TestUtcNow(unittest.TestCase):
    """Tests for _utc_now() — ISO UTC timestamp."""

    def test_returns_string(self):
        self.assertIsInstance(_utc_now(), str)

    def test_ends_with_z(self):
        self.assertTrue(_utc_now().endswith("Z"))

    def test_no_offset_string(self):
        self.assertNotIn("+00:00", _utc_now())

    def test_contains_t_separator(self):
        self.assertIn("T", _utc_now())


# ---------------------------------------------------------------------------
# _payload_hash
# ---------------------------------------------------------------------------


class TestPayloadHash(unittest.TestCase):
    """Tests for _payload_hash() — SHA-256 of canonicalized witness entry."""

    def test_returns_string(self):
        result = _payload_hash(1, "2026-01-01T00:00:00Z", None, {"key": "val"})
        self.assertIsInstance(result, str)

    def test_returns_64_hex_chars(self):
        result = _payload_hash(1, "2026-01-01T00:00:00Z", None, {})
        self.assertEqual(len(result), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_deterministic(self):
        args = (1, "2026-01-01T00:00:00Z", None, {"k": "v"})
        self.assertEqual(_payload_hash(*args), _payload_hash(*args))

    def test_different_seq_different_hash(self):
        h1 = _payload_hash(1, "2026-01-01T00:00:00Z", None, {})
        h2 = _payload_hash(2, "2026-01-01T00:00:00Z", None, {})
        self.assertNotEqual(h1, h2)

    def test_different_record_different_hash(self):
        h1 = _payload_hash(1, "2026-01-01T00:00:00Z", None, {"a": 1})
        h2 = _payload_hash(1, "2026-01-01T00:00:00Z", None, {"a": 2})
        self.assertNotEqual(h1, h2)

    def test_prev_hash_affects_output(self):
        h1 = _payload_hash(1, "2026-01-01T00:00:00Z", None, {})
        h2 = _payload_hash(1, "2026-01-01T00:00:00Z", "abc123", {})
        self.assertNotEqual(h1, h2)


# ---------------------------------------------------------------------------
# _last_commit
# ---------------------------------------------------------------------------


class TestLastCommit(unittest.TestCase):
    """Tests for _last_commit(path) — returns last valid JSON dict from JSONL."""

    def test_missing_file_returns_none(self):
        p = Path("/tmp/does_not_exist_99999.jsonl")
        self.assertIsNone(_last_commit(p))

    def test_empty_file_returns_none(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            p = Path(f.name)
        try:
            p.write_text("", encoding="utf-8")
            self.assertIsNone(_last_commit(p))
        finally:
            p.unlink(missing_ok=True)

    def test_single_json_dict_returned(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"seq": 1, "hash": "abc"}) + "\n")
            p = Path(f.name)
        try:
            result = _last_commit(p)
            self.assertIsNotNone(result)
            self.assertEqual(result["seq"], 1)
        finally:
            p.unlink(missing_ok=True)

    def test_returns_last_of_multiple(self):
        rows = [
            json.dumps({"seq": 1}),
            json.dumps({"seq": 2}),
            json.dumps({"seq": 3}),
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("\n".join(rows) + "\n")
            p = Path(f.name)
        try:
            result = _last_commit(p)
            self.assertEqual(result["seq"], 3)
        finally:
            p.unlink(missing_ok=True)

    def test_blank_lines_skipped(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("\n\n" + json.dumps({"seq": 5}) + "\n\n")
            p = Path(f.name)
        try:
            result = _last_commit(p)
            self.assertEqual(result["seq"], 5)
        finally:
            p.unlink(missing_ok=True)

    def test_corrupt_lines_skipped(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("not json\n" + json.dumps({"seq": 7}) + "\n")
            p = Path(f.name)
        try:
            result = _last_commit(p)
            self.assertEqual(result["seq"], 7)
        finally:
            p.unlink(missing_ok=True)

    def test_returns_dict(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"a": 1}) + "\n")
            p = Path(f.name)
        try:
            result = _last_commit(p)
            self.assertIsInstance(result, dict)
        finally:
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
