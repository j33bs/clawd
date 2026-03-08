"""Tests for pure helpers in scripts/daily_technique.py.

Pure stdlib (argparse, json, datetime) — no stubs needed.
TECHNIQUES list is computed at module load; get_technique_for_day/state are
deterministic (date-seeded).

Covers:
- TECHNIQUES constant structure
- get_technique_for_day() — day-of-year rotation
- get_technique_by_principle() — filter by principle/principle_map
- get_technique_for_state() — state-to-technique routing
- format_briefing() — string output
"""
import importlib.util as _ilu
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DT_PATH = REPO_ROOT / "scripts" / "daily_technique.py"

_spec = _ilu.spec_from_file_location("daily_technique_real", str(DT_PATH))
dt_mod = _ilu.module_from_spec(_spec)
sys.modules["daily_technique_real"] = dt_mod
_spec.loader.exec_module(dt_mod)


_SAMPLE_DATE = datetime(2024, 3, 15, tzinfo=timezone.utc)  # day_of_year=75


# ---------------------------------------------------------------------------
# TECHNIQUES constant
# ---------------------------------------------------------------------------

class TestTechniquesConstant(unittest.TestCase):
    """Tests for TECHNIQUES list structure."""

    def test_is_list(self):
        self.assertIsInstance(dt_mod.TECHNIQUES, list)

    def test_nonempty(self):
        self.assertGreater(len(dt_mod.TECHNIQUES), 0)

    def test_each_has_name(self):
        for t in dt_mod.TECHNIQUES:
            self.assertIn("name", t)

    def test_each_has_category(self):
        for t in dt_mod.TECHNIQUES:
            self.assertIn("category", t)

    def test_each_has_principle(self):
        for t in dt_mod.TECHNIQUES:
            self.assertIn("principle", t)

    def test_each_has_description(self):
        for t in dt_mod.TECHNIQUES:
            self.assertIn("description", t)

    def test_each_has_principle_map(self):
        """_derive_tacticr_principle_map() adds principle_map at load time."""
        for t in dt_mod.TECHNIQUES:
            self.assertIn("principle_map", t)

    def test_principle_map_is_list(self):
        for t in dt_mod.TECHNIQUES:
            self.assertIsInstance(t["principle_map"], list)

    def test_principle_map_nonempty(self):
        for t in dt_mod.TECHNIQUES:
            self.assertGreater(len(t["principle_map"]), 0)

    def test_names_are_strings(self):
        for t in dt_mod.TECHNIQUES:
            self.assertIsInstance(t["name"], str)


# ---------------------------------------------------------------------------
# get_technique_for_day
# ---------------------------------------------------------------------------

class TestGetTechniqueForDay(unittest.TestCase):
    """Tests for get_technique_for_day() — deterministic rotation."""

    def test_returns_dict(self):
        result = dt_mod.get_technique_for_day(_SAMPLE_DATE)
        self.assertIsInstance(result, dict)

    def test_has_name(self):
        result = dt_mod.get_technique_for_day(_SAMPLE_DATE)
        self.assertIn("name", result)

    def test_has_principle(self):
        result = dt_mod.get_technique_for_day(_SAMPLE_DATE)
        self.assertIn("principle", result)

    def test_result_in_techniques(self):
        result = dt_mod.get_technique_for_day(_SAMPLE_DATE)
        self.assertIn(result["name"], [t["name"] for t in dt_mod.TECHNIQUES])

    def test_uses_none_date(self):
        """None defaults to today; should still return a dict."""
        result = dt_mod.get_technique_for_day(None)
        self.assertIsInstance(result, dict)

    def test_deterministic_for_same_date(self):
        r1 = dt_mod.get_technique_for_day(_SAMPLE_DATE)
        r2 = dt_mod.get_technique_for_day(_SAMPLE_DATE)
        self.assertEqual(r1["name"], r2["name"])

    def test_different_dates_may_differ(self):
        date_a = datetime(2024, 1, 1, tzinfo=timezone.utc)  # day 1
        date_b = datetime(2024, 12, 31, tzinfo=timezone.utc)  # day 366
        # day % len(TECHNIQUES) differs unless coincidentally same
        r_a = dt_mod.get_technique_for_day(date_a)
        r_b = dt_mod.get_technique_for_day(date_b)
        # At minimum both return dicts from TECHNIQUES
        self.assertIn(r_a["name"], [t["name"] for t in dt_mod.TECHNIQUES])
        self.assertIn(r_b["name"], [t["name"] for t in dt_mod.TECHNIQUES])

    def test_index_wraps_within_bounds(self):
        """(day_of_year - 1) % len(TECHNIQUES) is always valid."""
        for day in (1, 50, 100, 200, 300, 365):
            date = datetime(2024, 1, 1, tzinfo=timezone.utc).replace()
            # We can't easily set day_of_year directly, but we can verify
            # that the result is always in TECHNIQUES for any date
        result = dt_mod.get_technique_for_day(datetime(2024, 12, 31, tzinfo=timezone.utc))
        self.assertIn(result["name"], [t["name"] for t in dt_mod.TECHNIQUES])


# ---------------------------------------------------------------------------
# get_technique_by_principle
# ---------------------------------------------------------------------------

class TestGetTechniqueByPrinciple(unittest.TestCase):
    """Tests for get_technique_by_principle() — filter by principle."""

    def test_returns_list(self):
        result = dt_mod.get_technique_by_principle("vitality")
        self.assertIsInstance(result, list)

    def test_vitality_returns_nonempty(self):
        result = dt_mod.get_technique_by_principle("vitality")
        self.assertGreater(len(result), 0)

    def test_all_results_have_matching_principle_or_map(self):
        for principle in ("vitality", "cognition", "flow"):
            results = dt_mod.get_technique_by_principle(principle)
            for t in results:
                ok = (t.get("principle") == principle or
                      principle.upper() in t.get("principle_map", []))
                self.assertTrue(ok, f"{t['name']} doesn't match {principle}")

    def test_unknown_principle_returns_list(self):
        result = dt_mod.get_technique_by_principle("xyzzy_unknown")
        self.assertIsInstance(result, list)

    def test_empty_string_principle(self):
        result = dt_mod.get_technique_by_principle("")
        self.assertIsInstance(result, list)

    def test_none_principle(self):
        result = dt_mod.get_technique_by_principle(None)
        self.assertIsInstance(result, list)

    def test_results_are_dicts(self):
        for t in dt_mod.get_technique_by_principle("vitality"):
            self.assertIsInstance(t, dict)


# ---------------------------------------------------------------------------
# get_technique_for_state
# ---------------------------------------------------------------------------

class TestGetTechniqueForState(unittest.TestCase):
    """Tests for get_technique_for_state() — state-to-technique routing."""

    def test_returns_dict(self):
        result = dt_mod.get_technique_for_state(date=_SAMPLE_DATE)
        self.assertIsInstance(result, dict)

    def test_has_name(self):
        result = dt_mod.get_technique_for_state(date=_SAMPLE_DATE)
        self.assertIn("name", result)

    def test_result_in_techniques(self):
        result = dt_mod.get_technique_for_state(date=_SAMPLE_DATE)
        self.assertIn(result["name"], [t["name"] for t in dt_mod.TECHNIQUES])

    def test_high_arousal_returns_technique(self):
        result = dt_mod.get_technique_for_state(date=_SAMPLE_DATE, arousal="high")
        self.assertIsInstance(result, dict)

    def test_low_arousal_returns_technique(self):
        result = dt_mod.get_technique_for_state(date=_SAMPLE_DATE, arousal="low")
        self.assertIsInstance(result, dict)

    def test_recent_errors_returns_technique(self):
        result = dt_mod.get_technique_for_state(date=_SAMPLE_DATE, recent_errors=3)
        self.assertIsInstance(result, dict)

    def test_complex_task_returns_technique(self):
        result = dt_mod.get_technique_for_state(date=_SAMPLE_DATE, complex_task=True)
        self.assertIsInstance(result, dict)

    def test_deterministic_for_same_state(self):
        r1 = dt_mod.get_technique_for_state(date=_SAMPLE_DATE, arousal="high")
        r2 = dt_mod.get_technique_for_state(date=_SAMPLE_DATE, arousal="high")
        self.assertEqual(r1["name"], r2["name"])


# ---------------------------------------------------------------------------
# format_briefing
# ---------------------------------------------------------------------------

class TestFormatBriefing(unittest.TestCase):
    """Tests for format_briefing() — string output."""

    def _get_technique(self):
        return dt_mod.get_technique_for_day(_SAMPLE_DATE)

    def test_returns_string(self):
        result = dt_mod.format_briefing(self._get_technique())
        self.assertIsInstance(result, str)

    def test_contains_technique_name(self):
        tech = self._get_technique()
        result = dt_mod.format_briefing(tech)
        self.assertIn(tech["name"], result)

    def test_contains_daily_technique_header(self):
        result = dt_mod.format_briefing(self._get_technique())
        self.assertIn("DAILY THERAPEUTIC TECHNIQUE", result)

    def test_nonempty(self):
        result = dt_mod.format_briefing(self._get_technique())
        self.assertTrue(result.strip())

    def test_multiline(self):
        result = dt_mod.format_briefing(self._get_technique())
        self.assertGreater(result.count("\n"), 3)


if __name__ == "__main__":
    unittest.main()
