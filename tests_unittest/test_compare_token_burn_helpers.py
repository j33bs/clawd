"""Tests for pure helpers in workspace/scripts/compare_token_burn.py.

Covers:
- _to_int(text, default=0) — safe int conversion
- _to_float(text, default=0.0) — safe float conversion
- _parse_thresholds(value) — threshold dict from JSON string or file
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "compare_token_burn.py"

_spec = _ilu.spec_from_file_location("compare_token_burn_real", str(SCRIPT_PATH))
_mod = _ilu.module_from_spec(_spec)
sys.modules["compare_token_burn_real"] = _mod
_spec.loader.exec_module(_mod)

_to_int = _mod._to_int
_to_float = _mod._to_float
_parse_thresholds = _mod._parse_thresholds
DEFAULT_THRESHOLDS = _mod.DEFAULT_THRESHOLDS


# ---------------------------------------------------------------------------
# _to_int
# ---------------------------------------------------------------------------


class TestToInt(unittest.TestCase):
    """Tests for _to_int() — safe integer conversion with default."""

    def test_integer_string(self):
        self.assertEqual(_to_int("42"), 42)

    def test_strips_whitespace(self):
        self.assertEqual(_to_int("  7  "), 7)

    def test_invalid_string_returns_default(self):
        self.assertEqual(_to_int("abc"), 0)

    def test_none_returns_default(self):
        self.assertEqual(_to_int(None), 0)

    def test_custom_default(self):
        self.assertEqual(_to_int("bad", default=99), 99)

    def test_zero_string(self):
        self.assertEqual(_to_int("0"), 0)

    def test_negative_string(self):
        self.assertEqual(_to_int("-5"), -5)

    def test_integer_input(self):
        # int passed directly: str(3) = "3" → int("3") = 3
        self.assertEqual(_to_int(3), 3)

    def test_float_string_returns_default(self):
        # "3.7" → int("3.7") raises ValueError → default 0
        self.assertEqual(_to_int("3.7"), 0)

    def test_returns_int_type(self):
        self.assertIsInstance(_to_int("10"), int)


# ---------------------------------------------------------------------------
# _to_float
# ---------------------------------------------------------------------------


class TestToFloat(unittest.TestCase):
    """Tests for _to_float() — safe float conversion with default."""

    def test_float_string(self):
        self.assertAlmostEqual(_to_float("3.14"), 3.14)

    def test_strips_whitespace(self):
        self.assertAlmostEqual(_to_float("  2.0  "), 2.0)

    def test_integer_string(self):
        self.assertAlmostEqual(_to_float("5"), 5.0)

    def test_invalid_string_returns_default(self):
        self.assertAlmostEqual(_to_float("abc"), 0.0)

    def test_none_returns_default(self):
        self.assertAlmostEqual(_to_float(None), 0.0)

    def test_custom_default(self):
        self.assertAlmostEqual(_to_float("bad", default=1.5), 1.5)

    def test_negative_float(self):
        self.assertAlmostEqual(_to_float("-0.5"), -0.5)

    def test_returns_float_type(self):
        self.assertIsInstance(_to_float("1.0"), float)


# ---------------------------------------------------------------------------
# _parse_thresholds
# ---------------------------------------------------------------------------


class TestParseThresholds(unittest.TestCase):
    """Tests for _parse_thresholds() — JSON-string or file to threshold dict."""

    def test_none_returns_defaults(self):
        result = _parse_thresholds(None)
        self.assertEqual(result, DEFAULT_THRESHOLDS)

    def test_empty_string_returns_defaults(self):
        result = _parse_thresholds("")
        self.assertEqual(result, DEFAULT_THRESHOLDS)

    def test_whitespace_only_returns_defaults(self):
        result = _parse_thresholds("   ")
        self.assertEqual(result, DEFAULT_THRESHOLDS)

    def test_returns_dict(self):
        self.assertIsInstance(_parse_thresholds(None), dict)

    def test_returns_copy_not_original(self):
        a = _parse_thresholds(None)
        b = _parse_thresholds(None)
        a["new_key"] = 999
        self.assertNotIn("new_key", b)

    def test_valid_json_string_merged(self):
        override = json.dumps({"max_failure_rate_pp": 99.0})
        result = _parse_thresholds(override)
        self.assertAlmostEqual(result["max_failure_rate_pp"], 99.0)

    def test_valid_json_preserves_other_defaults(self):
        override = json.dumps({"max_failure_rate_pp": 99.0})
        result = _parse_thresholds(override)
        # Other default keys still present
        self.assertIn("max_timeout_waste_delta_tokens", result)

    def test_invalid_json_string_returns_defaults(self):
        result = _parse_thresholds("not-json-{{")
        self.assertEqual(result, DEFAULT_THRESHOLDS)

    def test_json_file_path_merged(self):
        data = {"max_failure_rate_pp": 55.0}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            p = Path(f.name)
        try:
            result = _parse_thresholds(str(p))
            self.assertAlmostEqual(result["max_failure_rate_pp"], 55.0)
        finally:
            p.unlink(missing_ok=True)

    def test_nonexistent_path_returns_defaults(self):
        # A path that doesn't exist AND is not valid JSON
        result = _parse_thresholds("/tmp/does_not_exist_abc123xyz.json")
        self.assertEqual(result, DEFAULT_THRESHOLDS)

    def test_all_default_keys_present(self):
        result = _parse_thresholds(None)
        for key in DEFAULT_THRESHOLDS:
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
