"""Tests for workspace/time_management/time_management.py pure helpers.

Covers (no live file writes beyond tempfile):
- _get_time_category
- _load_json / _save_json
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
TM_DIR = REPO_ROOT / "workspace" / "time_management"
if str(TM_DIR) not in sys.path:
    sys.path.insert(0, str(TM_DIR))

from time_management import _get_time_category, _load_json, _save_json  # noqa: E402


# ---------------------------------------------------------------------------
# _get_time_category
# ---------------------------------------------------------------------------

def _mock_now(hour: int):
    """Return a mock for time_management.datetime.now that returns given hour."""
    from unittest.mock import MagicMock
    from datetime import datetime
    mock_dt = MagicMock()
    mock_dt.now.return_value = datetime(2026, 3, 8, hour, 0, 0)
    return patch("time_management.datetime", mock_dt)


class TestGetTimeCategory(unittest.TestCase):
    """Tests for _get_time_category() — hour → time bucket string."""

    def test_morning_boundary(self):
        with _mock_now(5):
            import time_management as tm
            result = tm._get_time_category()
        self.assertEqual(result, "morning")

    def test_midday(self):
        with _mock_now(11):
            import time_management as tm
            result = tm._get_time_category()
        self.assertEqual(result, "midday")

    def test_afternoon(self):
        with _mock_now(15):
            import time_management as tm
            result = tm._get_time_category()
        self.assertEqual(result, "afternoon")

    def test_evening(self):
        with _mock_now(19):
            import time_management as tm
            result = tm._get_time_category()
        self.assertEqual(result, "evening")

    def test_night(self):
        with _mock_now(23):
            import time_management as tm
            result = tm._get_time_category()
        self.assertEqual(result, "night")

    def test_night_early_morning(self):
        with _mock_now(2):
            import time_management as tm
            result = tm._get_time_category()
        self.assertEqual(result, "night")

    def test_returns_string(self):
        result = _get_time_category()
        self.assertIsInstance(result, str)

    def test_returns_known_category(self):
        result = _get_time_category()
        self.assertIn(result, {"morning", "midday", "afternoon", "evening", "night"})


# ---------------------------------------------------------------------------
# _load_json / _save_json
# ---------------------------------------------------------------------------

class TestLoadJson(unittest.TestCase):
    """Tests for _load_json() — returns default when file missing."""

    def test_missing_file_returns_default(self):
        result = _load_json(Path("/nonexistent/path.json"), {"default": True})
        self.assertEqual(result, {"default": True})

    def test_existing_file_loaded(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "data.json"
            path.write_text(json.dumps({"key": "val"}), encoding="utf-8")
            result = _load_json(path, {})
            self.assertEqual(result["key"], "val")

    def test_returns_dict(self):
        result = _load_json(Path("/nonexistent"), {})
        self.assertIsInstance(result, dict)


class TestSaveJson(unittest.TestCase):
    """Tests for _save_json() — writes JSON to file."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "out.json"
            _save_json(path, {"x": 1})
            self.assertTrue(path.exists())

    def test_content_correct(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "out.json"
            _save_json(path, {"answer": 42})
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["answer"], 42)

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rt.json"
            original = {"a": [1, 2, 3], "b": "hello"}
            _save_json(path, original)
            loaded = _load_json(path, {})
            self.assertEqual(loaded, original)


if __name__ == "__main__":
    unittest.main()
