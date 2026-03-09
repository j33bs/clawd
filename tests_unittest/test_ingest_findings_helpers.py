"""Tests for pure helpers in workspace/scripts/ingest_findings.py.

Covers:
- _utc_now() — ISO UTC timestamp ending in 'Z'
- _entry_key(q) — stable 16-char SHA-256 hash key from question dict
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "ingest_findings.py"

_spec = _ilu.spec_from_file_location("ingest_findings_real", str(SCRIPT_PATH))
_mod = _ilu.module_from_spec(_spec)
sys.modules["ingest_findings_real"] = _mod
_spec.loader.exec_module(_mod)

_utc_now = _mod._utc_now
_entry_key = _mod._entry_key


# ---------------------------------------------------------------------------
# _utc_now
# ---------------------------------------------------------------------------


class TestUtcNow(unittest.TestCase):
    """Tests for _utc_now() — ISO UTC timestamp string."""

    def test_returns_string(self):
        self.assertIsInstance(_utc_now(), str)

    def test_ends_with_z(self):
        self.assertTrue(_utc_now().endswith("Z"))

    def test_no_offset_string(self):
        self.assertNotIn("+00:00", _utc_now())

    def test_contains_t_separator(self):
        self.assertIn("T", _utc_now())


# ---------------------------------------------------------------------------
# _entry_key
# ---------------------------------------------------------------------------


class TestEntryKey(unittest.TestCase):
    """Tests for _entry_key() — 16-char hex hash of question entry."""

    def test_returns_string(self):
        result = _entry_key({"from_topic": "test", "timestamp": "2026-01-01"})
        self.assertIsInstance(result, str)

    def test_returns_16_chars(self):
        result = _entry_key({"from_topic": "abc", "timestamp": "ts"})
        self.assertEqual(len(result), 16)

    def test_all_hex_chars(self):
        result = _entry_key({"from_topic": "x", "timestamp": "y"})
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_deterministic(self):
        q = {"from_topic": "topic", "timestamp": "2026-01-01T00:00:00Z"}
        self.assertEqual(_entry_key(q), _entry_key(q))

    def test_different_inputs_different_keys(self):
        a = _entry_key({"from_topic": "alpha", "timestamp": "t1"})
        b = _entry_key({"from_topic": "beta", "timestamp": "t1"})
        self.assertNotEqual(a, b)

    def test_different_timestamps_different_keys(self):
        a = _entry_key({"from_topic": "t", "timestamp": "2026-01-01"})
        b = _entry_key({"from_topic": "t", "timestamp": "2026-01-02"})
        self.assertNotEqual(a, b)

    def test_empty_dict_handled(self):
        result = _entry_key({})
        self.assertEqual(len(result), 16)

    def test_extra_fields_ignored(self):
        # _entry_key only uses from_topic and timestamp
        a = _entry_key({"from_topic": "x", "timestamp": "y"})
        b = _entry_key({"from_topic": "x", "timestamp": "y", "extra": "ignored"})
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
