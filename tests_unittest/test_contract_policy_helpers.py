"""Tests for pure helpers in workspace/scripts/contract_policy.py.

Covers:
- _parse_z(value) — ISO timestamp parser → UTC-aware datetime or None
- contract_allows_code(contract) — mode == "CODE" check
"""
import importlib.util as _ilu
import sys
import unittest
from datetime import timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "contract_policy.py"

_spec = _ilu.spec_from_file_location("contract_policy_real", str(SCRIPT_PATH))
_mod = _ilu.module_from_spec(_spec)
sys.modules["contract_policy_real"] = _mod
_spec.loader.exec_module(_mod)

_parse_z = _mod._parse_z
contract_allows_code = _mod.contract_allows_code


# ---------------------------------------------------------------------------
# _parse_z
# ---------------------------------------------------------------------------


class TestParseZ(unittest.TestCase):
    """Tests for _parse_z() — flexible ISO-8601 parser → UTC datetime."""

    def test_none_returns_none(self):
        self.assertIsNone(_parse_z(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_z(""))

    def test_whitespace_returns_none(self):
        self.assertIsNone(_parse_z("   "))

    def test_invalid_returns_none(self):
        self.assertIsNone(_parse_z("not-a-date"))

    def test_z_suffix_parsed(self):
        result = _parse_z("2026-01-01T00:00:00Z")
        self.assertIsNotNone(result)

    def test_offset_parsed(self):
        result = _parse_z("2026-01-01T00:00:00+00:00")
        self.assertIsNotNone(result)

    def test_returns_utc_datetime(self):
        result = _parse_z("2026-03-01T12:00:00Z")
        import datetime as dt
        self.assertEqual(result.tzinfo, dt.timezone.utc)

    def test_z_and_offset_same_result(self):
        a = _parse_z("2026-01-15T08:00:00Z")
        b = _parse_z("2026-01-15T08:00:00+00:00")
        self.assertEqual(a, b)

    def test_non_utc_offset_converted_to_utc(self):
        # "+05:30" → should be in UTC
        result = _parse_z("2026-01-01T05:30:00+05:30")
        self.assertIsNotNone(result)
        import datetime as dt
        self.assertEqual(result.tzinfo, dt.timezone.utc)
        # 05:30+05:30 = 00:00 UTC
        self.assertEqual(result.hour, 0)
        self.assertEqual(result.minute, 0)

    def test_naive_datetime_gets_utc(self):
        # Naive datetime (no tzinfo) → UTC applied
        result = _parse_z("2026-01-01T00:00:00")
        self.assertIsNotNone(result)
        import datetime as dt
        self.assertEqual(result.tzinfo, dt.timezone.utc)

    def test_correct_year_month_day(self):
        result = _parse_z("2026-03-09T00:00:00Z")
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.day, 9)

    def test_falsy_zero_returns_none(self):
        self.assertIsNone(_parse_z(0))


# ---------------------------------------------------------------------------
# contract_allows_code
# ---------------------------------------------------------------------------


class TestContractAllowsCode(unittest.TestCase):
    """Tests for contract_allows_code() — mode == 'CODE' check."""

    def test_uppercase_code_true(self):
        self.assertTrue(contract_allows_code({"mode": "CODE"}))

    def test_lowercase_code_true(self):
        self.assertTrue(contract_allows_code({"mode": "code"}))

    def test_mixed_case_code_true(self):
        self.assertTrue(contract_allows_code({"mode": "Code"}))

    def test_chat_mode_false(self):
        self.assertFalse(contract_allows_code({"mode": "CHAT"}))

    def test_no_mode_key_false(self):
        self.assertFalse(contract_allows_code({}))

    def test_none_mode_false(self):
        self.assertFalse(contract_allows_code({"mode": None}))

    def test_empty_mode_false(self):
        self.assertFalse(contract_allows_code({"mode": ""}))

    def test_returns_bool(self):
        self.assertIsInstance(contract_allows_code({"mode": "CODE"}), bool)


if __name__ == "__main__":
    unittest.main()
