"""Tests for workspace/hivemind/hivemind/intelligence/suggestions.py pure helpers.

Covers (no HiveMindStore network calls):
- _iso
- _can_view
- _load_state
- _save_state
"""
import json
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"

# Stub HiveMindStore before import.
_hm_pkg = types.ModuleType("hivemind")
_hm_pkg.__path__ = [str(HIVEMIND_ROOT / "hivemind")]
_store_mod = types.ModuleType("hivemind.store")
_store_mod.HiveMindStore = type("HiveMindStore", (), {})
sys.modules.setdefault("hivemind", _hm_pkg)
sys.modules.setdefault("hivemind.store", _store_mod)

if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.intelligence import suggestions as sg  # noqa: E402


_UTC = timezone.utc


# ---------------------------------------------------------------------------
# _iso
# ---------------------------------------------------------------------------

class TestIso(unittest.TestCase):
    """Tests for _iso() — ISO timestamp string → UTC-aware datetime."""

    def test_z_suffix_parsed(self):
        result = sg._iso("2026-01-15T12:00:00Z")
        self.assertEqual(result.hour, 12)

    def test_naive_becomes_utc(self):
        result = sg._iso("2026-01-15T12:00:00")
        self.assertEqual(result.tzinfo, _UTC)

    def test_returns_datetime(self):
        self.assertIsInstance(sg._iso("2026-01-15T12:00:00"), datetime)

    def test_offset_timestamp_parsed(self):
        result = sg._iso("2026-01-15T14:00:00+02:00")
        self.assertIsNotNone(result.tzinfo)

    def test_year_month_day(self):
        result = sg._iso("2026-03-08T00:00:00")
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.day, 8)


# ---------------------------------------------------------------------------
# _can_view
# ---------------------------------------------------------------------------

class TestCanView(unittest.TestCase):
    """Tests for _can_view() — agent scope visibility check."""

    def test_shared_scope_always_visible(self):
        self.assertTrue(sg._can_view("main", "shared"))

    def test_matching_agent_scope_visible(self):
        self.assertTrue(sg._can_view("main", "main"))

    def test_different_agent_scope_not_visible(self):
        self.assertFalse(sg._can_view("main", "codex"))

    def test_codex_sees_own_scope(self):
        self.assertTrue(sg._can_view("codex", "codex"))

    def test_returns_bool(self):
        self.assertIsInstance(sg._can_view("a", "b"), bool)


# ---------------------------------------------------------------------------
# _load_state
# ---------------------------------------------------------------------------

class TestLoadState(unittest.TestCase):
    """Tests for _load_state() — reads JSON or returns default."""

    def test_missing_file_returns_default(self):
        result = sg._load_state(Path("/nonexistent/path.json"))
        self.assertEqual(result, {"sessions": {}})

    def test_existing_file_loaded(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            path.write_text(json.dumps({"sessions": {"x": 1}}), encoding="utf-8")
            result = sg._load_state(path)
            self.assertEqual(result["sessions"]["x"], 1)

    def test_invalid_json_returns_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.json"
            path.write_text("NOT JSON", encoding="utf-8")
            result = sg._load_state(path)
            self.assertEqual(result, {"sessions": {}})

    def test_returns_dict(self):
        result = sg._load_state(Path("/no/file"))
        self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# _save_state
# ---------------------------------------------------------------------------

class TestSaveState(unittest.TestCase):
    """Tests for _save_state() — writes state JSON to file."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            sg._save_state({"sessions": {}}, path)
            self.assertTrue(path.exists())

    def test_content_correct(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            state = {"sessions": {"s1": {"count": 3}}}
            sg._save_state(state, path)
            reloaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(reloaded["sessions"]["s1"]["count"], 3)

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            original = {"sessions": {"a": {"count": 1, "last": "2026-01-01T00:00:00Z"}}}
            sg._save_state(original, path)
            result = sg._load_state(path)
            self.assertEqual(result, original)

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nested" / "dir" / "state.json"
            sg._save_state({"sessions": {}}, path)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
