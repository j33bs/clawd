"""Tests for workspace/memory/relationship_tracker.py pure helpers.

No external deps — stdlib only (json, pathlib). Loaded with a unique module name.

Covers:
- _resolve_path
- _default_state
- _tone_adjustment
- _clamp
- load_state
- save_state
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = _ilu.spec_from_file_location(
    "relationship_tracker_real",
    str(REPO_ROOT / "workspace" / "memory" / "relationship_tracker.py"),
)
rt = _ilu.module_from_spec(_spec)
sys.modules["relationship_tracker_real"] = rt
_spec.loader.exec_module(rt)


# ---------------------------------------------------------------------------
# _resolve_path
# ---------------------------------------------------------------------------

class TestResolvePath(unittest.TestCase):
    """Tests for _resolve_path() — resolves state JSON path."""

    def test_absolute_state_path_returned_as_is(self):
        p = Path("/tmp/absolute/state.json")
        result = rt._resolve_path("/repo", state_path=p)
        self.assertEqual(result, p)

    def test_none_state_path_uses_default(self):
        result = rt._resolve_path("/repo", state_path=None)
        self.assertTrue(str(result).startswith("/repo"))
        self.assertIn("relationship_state.json", str(result))

    def test_relative_state_path_prefixed(self):
        p = Path("custom/state.json")
        result = rt._resolve_path("/repo", state_path=p)
        self.assertEqual(result, Path("/repo") / p)

    def test_returns_path(self):
        result = rt._resolve_path("/repo")
        self.assertIsInstance(result, Path)


# ---------------------------------------------------------------------------
# _default_state
# ---------------------------------------------------------------------------

class TestDefaultState(unittest.TestCase):
    """Tests for _default_state() — factory for fresh state dict."""

    def test_has_schema_key(self):
        result = rt._default_state()
        self.assertIn("schema", result)

    def test_has_sessions_key(self):
        result = rt._default_state()
        self.assertIn("sessions", result)

    def test_has_updated_at_key(self):
        result = rt._default_state()
        self.assertIn("updated_at", result)

    def test_sessions_is_empty_dict(self):
        result = rt._default_state()
        self.assertEqual(result["sessions"], {})

    def test_returns_dict(self):
        result = rt._default_state()
        self.assertIsInstance(result, dict)

    def test_returns_fresh_dict_each_call(self):
        a = rt._default_state()
        b = rt._default_state()
        a["sessions"]["x"] = 1
        self.assertNotIn("x", b["sessions"])


# ---------------------------------------------------------------------------
# _tone_adjustment
# ---------------------------------------------------------------------------

class TestToneAdjustment(unittest.TestCase):
    """Tests for _tone_adjustment() — maps tone label to trust delta."""

    def test_supportive_positive(self):
        self.assertAlmostEqual(rt._tone_adjustment("supportive"), 0.03)

    def test_warm_positive(self):
        self.assertAlmostEqual(rt._tone_adjustment("warm"), 0.03)

    def test_calm_positive(self):
        self.assertAlmostEqual(rt._tone_adjustment("calm"), 0.03)

    def test_positive_label_positive(self):
        self.assertAlmostEqual(rt._tone_adjustment("positive"), 0.03)

    def test_hostile_negative(self):
        self.assertAlmostEqual(rt._tone_adjustment("hostile"), -0.04)

    def test_frustrated_negative(self):
        self.assertAlmostEqual(rt._tone_adjustment("frustrated"), -0.04)

    def test_neutral_label_zero(self):
        self.assertAlmostEqual(rt._tone_adjustment("neutral"), 0.0)

    def test_empty_string_zero(self):
        self.assertAlmostEqual(rt._tone_adjustment(""), 0.0)

    def test_unknown_label_zero(self):
        self.assertAlmostEqual(rt._tone_adjustment("unlabeled"), 0.0)

    def test_case_insensitive(self):
        self.assertAlmostEqual(rt._tone_adjustment("SUPPORTIVE"), 0.03)
        self.assertAlmostEqual(rt._tone_adjustment("Hostile"), -0.04)

    def test_returns_float(self):
        result = rt._tone_adjustment("neutral")
        self.assertIsInstance(result, float)


# ---------------------------------------------------------------------------
# _clamp
# ---------------------------------------------------------------------------

class TestClamp(unittest.TestCase):
    """Tests for _clamp() — clamp float value between lo and hi."""

    def test_value_below_lo(self):
        self.assertAlmostEqual(rt._clamp(-1.0, 0.0, 1.0), 0.0)

    def test_value_above_hi(self):
        self.assertAlmostEqual(rt._clamp(2.0, 0.0, 1.0), 1.0)

    def test_value_in_range(self):
        self.assertAlmostEqual(rt._clamp(0.5, 0.0, 1.0), 0.5)

    def test_value_at_lo(self):
        self.assertAlmostEqual(rt._clamp(0.0, 0.0, 1.0), 0.0)

    def test_value_at_hi(self):
        self.assertAlmostEqual(rt._clamp(1.0, 0.0, 1.0), 1.0)

    def test_returns_float(self):
        result = rt._clamp(0.5, 0.0, 1.0)
        self.assertIsInstance(result, float)


# ---------------------------------------------------------------------------
# load_state
# ---------------------------------------------------------------------------

class TestLoadState(unittest.TestCase):
    """Tests for load_state() — loads state JSON or returns defaults."""

    def test_missing_file_returns_defaults(self):
        result = rt.load_state(repo_root="/nonexistent/repo")
        self.assertIn("schema", result)
        self.assertIn("sessions", result)

    def test_valid_json_merged(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            p.write_text(json.dumps({"schema": 2, "sessions": {"s1": {}}}), encoding="utf-8")
            result = rt.load_state(repo_root=td, state_path=p)
            self.assertEqual(result["schema"], 2)
            self.assertIn("s1", result["sessions"])

    def test_invalid_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            p.write_text("NOT JSON", encoding="utf-8")
            result = rt.load_state(repo_root=td, state_path=p)
            self.assertEqual(result["sessions"], {})

    def test_non_dict_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            result = rt.load_state(repo_root=td, state_path=p)
            self.assertEqual(result["sessions"], {})

    def test_returns_dict(self):
        result = rt.load_state(repo_root="/no/path")
        self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# save_state
# ---------------------------------------------------------------------------

class TestSaveState(unittest.TestCase):
    """Tests for save_state() — writes state dict to JSON file."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "state.json"
            rt.save_state({"schema": 1, "sessions": {}}, repo_root=td, state_path=p)
            self.assertTrue(p.exists())

    def test_content_is_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            rt.save_state({"schema": 1, "sessions": {"s": {}}}, repo_root=td, state_path=p)
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertIn("s", data["sessions"])

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            result = rt.save_state({"schema": 1}, repo_root=td, state_path=p)
            self.assertIsInstance(result, Path)

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a" / "b" / "state.json"
            rt.save_state({"schema": 1}, repo_root=td, state_path=p)
            self.assertTrue(p.parent.is_dir())


if __name__ == "__main__":
    unittest.main()
