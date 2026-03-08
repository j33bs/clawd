"""Tests for pure helpers in workspace/scripts/verify_tacti_cr_events.py.

Uses real workspace.tacti_cr.events for the import; only tests the
pure _parse_min_count() helper.

Covers:
- _parse_min_count() — parses 'type=n' pairs into dict[str, int]
"""
import importlib.util as _ilu
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "verify_tacti_cr_events.py"

# The script patches sys.path[0] to WORKSPACE_ROOT; ensure workspace is importable.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_spec = _ilu.spec_from_file_location("verify_tacti_cr_real", str(SCRIPT_PATH))
vtce = _ilu.module_from_spec(_spec)
sys.modules["verify_tacti_cr_real"] = vtce
_spec.loader.exec_module(vtce)

_parse_min_count = vtce._parse_min_count


# ---------------------------------------------------------------------------
# _parse_min_count
# ---------------------------------------------------------------------------

class TestParseMinCount(unittest.TestCase):
    """Tests for _parse_min_count() — 'type=n' string list → dict."""

    def test_returns_dict(self):
        result = _parse_min_count([])
        self.assertIsInstance(result, dict)

    def test_empty_list_returns_empty_dict(self):
        result = _parse_min_count([])
        self.assertEqual(result, {})

    def test_single_valid_entry(self):
        result = _parse_min_count(["heartbeat=5"])
        self.assertEqual(result, {"heartbeat": 5})

    def test_multiple_valid_entries(self):
        result = _parse_min_count(["a=1", "b=2", "c=3"])
        self.assertEqual(result, {"a": 1, "b": 2, "c": 3})

    def test_value_is_int(self):
        result = _parse_min_count(["x=42"])
        self.assertIsInstance(result["x"], int)

    def test_raises_on_missing_equals(self):
        with self.assertRaises(ValueError):
            _parse_min_count(["no-equals"])

    def test_raises_on_empty_key(self):
        with self.assertRaises(ValueError):
            _parse_min_count(["=5"])

    def test_raises_on_space_key(self):
        """Key with only spaces strips to empty → ValueError."""
        with self.assertRaises(ValueError):
            _parse_min_count(["  =5"])

    def test_raises_on_non_int_value(self):
        with self.assertRaises(ValueError):
            _parse_min_count(["type=notanumber"])

    def test_allows_equals_in_value(self):
        """Splits only on first '=' — extras in value cause ValueError (not int)."""
        with self.assertRaises(ValueError):
            _parse_min_count(["type=1=2"])

    def test_type_with_underscore(self):
        result = _parse_min_count(["some_type=10"])
        self.assertEqual(result["some_type"], 10)

    def test_large_count(self):
        result = _parse_min_count(["events=99999"])
        self.assertEqual(result["events"], 99999)

    def test_zero_value(self):
        result = _parse_min_count(["type=0"])
        self.assertEqual(result["type"], 0)

    def test_key_whitespace_stripped(self):
        """Key is stripped before use."""
        result = _parse_min_count(["  mytype  =7"])
        self.assertEqual(result["mytype"], 7)


if __name__ == "__main__":
    unittest.main()
