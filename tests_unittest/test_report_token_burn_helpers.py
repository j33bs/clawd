"""Tests for pure helpers in workspace/scripts/report_token_burn.py.

Covers:
- _safe_int(value, default=0) — safe integer conversion
- _parse_since(value) — timestamp string → milliseconds since epoch
- _event_timestamp(value) — numeric/string timestamp normalisation
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "report_token_burn.py"

_spec = _ilu.spec_from_file_location("report_token_burn_real", str(SCRIPT_PATH))
_mod = _ilu.module_from_spec(_spec)
sys.modules["report_token_burn_real"] = _mod
_spec.loader.exec_module(_mod)

_safe_int = _mod._safe_int
_parse_since = _mod._parse_since
_event_timestamp = _mod._event_timestamp


# ---------------------------------------------------------------------------
# _safe_int
# ---------------------------------------------------------------------------


class TestSafeInt(unittest.TestCase):
    """Tests for _safe_int() — safe int conversion with default."""

    def test_integer_value(self):
        self.assertEqual(_safe_int(42), 42)

    def test_string_integer(self):
        self.assertEqual(_safe_int("100"), 100)

    def test_invalid_string_returns_default(self):
        self.assertEqual(_safe_int("abc"), 0)

    def test_none_returns_default(self):
        self.assertEqual(_safe_int(None), 0)

    def test_custom_default(self):
        self.assertEqual(_safe_int("bad", default=99), 99)

    def test_float_value_truncated(self):
        # int(3.9) = 3
        self.assertEqual(_safe_int(3.9), 3)

    def test_zero(self):
        self.assertEqual(_safe_int(0), 0)

    def test_negative(self):
        self.assertEqual(_safe_int(-5), -5)

    def test_returns_int_type(self):
        self.assertIsInstance(_safe_int("7"), int)


# ---------------------------------------------------------------------------
# _parse_since
# ---------------------------------------------------------------------------


class TestParseSince(unittest.TestCase):
    """Tests for _parse_since() — timestamp → milliseconds since epoch."""

    def test_none_returns_none(self):
        self.assertIsNone(_parse_since(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_since(""))

    def test_whitespace_returns_none(self):
        self.assertIsNone(_parse_since("   "))

    def test_invalid_returns_none(self):
        self.assertIsNone(_parse_since("not-a-timestamp"))

    def test_large_float_returned_as_is(self):
        # > 1e12 → treated as ms directly
        ms = 1_700_000_000_000  # 1.7e12
        result = _parse_since(str(float(ms)))
        self.assertEqual(result, ms)

    def test_small_float_multiplied_by_1000(self):
        # <= 1e12 → treated as seconds → *1000
        secs = 1_700_000.0  # well below 1e12
        result = _parse_since(str(secs))
        self.assertEqual(result, int(secs * 1000))

    def test_iso_z_timestamp_returns_int(self):
        result = _parse_since("2026-01-01T00:00:00Z")
        self.assertIsInstance(result, int)
        # Should be positive (> 0)
        self.assertGreater(result, 0)

    def test_iso_offset_timestamp_returns_int(self):
        result = _parse_since("2026-01-01T00:00:00+00:00")
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0)

    def test_iso_z_and_offset_same_result(self):
        a = _parse_since("2026-03-01T12:00:00Z")
        b = _parse_since("2026-03-01T12:00:00+00:00")
        self.assertEqual(a, b)


# ---------------------------------------------------------------------------
# _event_timestamp
# ---------------------------------------------------------------------------


class TestEventTimestamp(unittest.TestCase):
    """Tests for _event_timestamp() — normalises various timestamp types to ms."""

    def test_none_returns_none(self):
        self.assertIsNone(_event_timestamp(None))

    def test_large_int_returned_as_is(self):
        ms = 1_700_000_000_001
        self.assertEqual(_event_timestamp(ms), ms)

    def test_small_int_multiplied_by_1000(self):
        secs = 1_700_000
        self.assertEqual(_event_timestamp(secs), secs * 1000)

    def test_large_float_converted_to_int(self):
        ms_float = 1_700_000_000_001.0
        result = _event_timestamp(ms_float)
        self.assertIsInstance(result, int)
        self.assertEqual(result, int(ms_float))

    def test_small_float_multiplied_by_1000(self):
        secs = 1_700_000.5
        result = _event_timestamp(secs)
        self.assertEqual(result, int(secs * 1000))

    def test_string_delegates_to_parse_since(self):
        # ISO string should be parsed to ms
        result = _event_timestamp("2026-01-01T00:00:00Z")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, int)

    def test_unknown_type_returns_none(self):
        self.assertIsNone(_event_timestamp([1, 2, 3]))

    def test_dict_returns_none(self):
        self.assertIsNone(_event_timestamp({"ts": 123}))


if __name__ == "__main__":
    unittest.main()
