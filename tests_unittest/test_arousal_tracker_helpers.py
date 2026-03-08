"""Tests for workspace/memory/arousal_tracker.py pure helpers.

Stdlib-only (json, pathlib). Loaded with a unique module name.

Covers:
- _resolve_path
- _default_state
- _tone_to_energy
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
    "arousal_tracker_real",
    str(REPO_ROOT / "workspace" / "memory" / "arousal_tracker.py"),
)
at = _ilu.module_from_spec(_spec)
sys.modules["arousal_tracker_real"] = at
_spec.loader.exec_module(at)


# ---------------------------------------------------------------------------
# _resolve_path
# ---------------------------------------------------------------------------

class TestResolvePath(unittest.TestCase):
    """Tests for _resolve_path() — resolves arousal state path."""

    def test_absolute_state_path_returned_as_is(self):
        p = Path("/tmp/absolute/state.json")
        result = at._resolve_path("/repo", state_path=p)
        self.assertEqual(result, p)

    def test_none_uses_default_relative_to_root(self):
        result = at._resolve_path("/repo", state_path=None)
        self.assertTrue(str(result).startswith("/repo"))
        self.assertIn("arousal_state.json", str(result))

    def test_relative_path_prefixed(self):
        p = Path("custom/state.json")
        result = at._resolve_path("/repo", state_path=p)
        self.assertEqual(result, Path("/repo") / p)

    def test_returns_path(self):
        self.assertIsInstance(at._resolve_path("/repo"), Path)


# ---------------------------------------------------------------------------
# _default_state
# ---------------------------------------------------------------------------

class TestDefaultState(unittest.TestCase):
    """Tests for _default_state() — creates a fresh arousal state dict."""

    def test_has_schema_key(self):
        self.assertIn("schema", at._default_state())

    def test_has_sessions_key(self):
        self.assertIn("sessions", at._default_state())

    def test_has_updated_at_key(self):
        self.assertIn("updated_at", at._default_state())

    def test_sessions_is_empty_dict(self):
        self.assertEqual(at._default_state()["sessions"], {})

    def test_independent_copies(self):
        a = at._default_state()
        b = at._default_state()
        a["sessions"]["x"] = 1
        self.assertNotIn("x", b["sessions"])


# ---------------------------------------------------------------------------
# _tone_to_energy
# ---------------------------------------------------------------------------

class TestToneToEnergy(unittest.TestCase):
    """Tests for _tone_to_energy() — maps tone label to energy level."""

    def test_high_returns_085(self):
        self.assertAlmostEqual(at._tone_to_energy("high"), 0.85)

    def test_urgent_returns_085(self):
        self.assertAlmostEqual(at._tone_to_energy("urgent"), 0.85)

    def test_stressed_returns_085(self):
        self.assertAlmostEqual(at._tone_to_energy("stressed"), 0.85)

    def test_excited_returns_085(self):
        self.assertAlmostEqual(at._tone_to_energy("excited"), 0.85)

    def test_low_returns_030(self):
        self.assertAlmostEqual(at._tone_to_energy("low"), 0.30)

    def test_calm_returns_030(self):
        self.assertAlmostEqual(at._tone_to_energy("calm"), 0.30)

    def test_flat_returns_030(self):
        self.assertAlmostEqual(at._tone_to_energy("flat"), 0.30)

    def test_unknown_returns_050(self):
        self.assertAlmostEqual(at._tone_to_energy("neutral"), 0.50)

    def test_empty_returns_050(self):
        self.assertAlmostEqual(at._tone_to_energy(""), 0.50)

    def test_case_insensitive(self):
        self.assertAlmostEqual(at._tone_to_energy("HIGH"), 0.85)
        self.assertAlmostEqual(at._tone_to_energy("Calm"), 0.30)

    def test_returns_float(self):
        self.assertIsInstance(at._tone_to_energy("high"), float)


# ---------------------------------------------------------------------------
# _clamp
# ---------------------------------------------------------------------------

class TestClamp(unittest.TestCase):
    """Tests for _clamp() — clamps float between lo and hi."""

    def test_below_lo(self):
        self.assertAlmostEqual(at._clamp(-1.0, 0.0, 1.0), 0.0)

    def test_above_hi(self):
        self.assertAlmostEqual(at._clamp(2.0, 0.0, 1.0), 1.0)

    def test_in_range(self):
        self.assertAlmostEqual(at._clamp(0.5, 0.0, 1.0), 0.5)

    def test_at_boundary(self):
        self.assertAlmostEqual(at._clamp(0.0, 0.0, 1.0), 0.0)
        self.assertAlmostEqual(at._clamp(1.0, 0.0, 1.0), 1.0)


# ---------------------------------------------------------------------------
# load_state
# ---------------------------------------------------------------------------

class TestLoadState(unittest.TestCase):
    """Tests for load_state() — reads JSON or returns defaults."""

    def test_missing_file_returns_defaults(self):
        result = at.load_state(repo_root="/nonexistent")
        self.assertIn("sessions", result)

    def test_valid_json_merged(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            p.write_text(json.dumps({"schema": 2, "sessions": {"s": {}}}), encoding="utf-8")
            result = at.load_state(repo_root=td, state_path=p)
            self.assertEqual(result["schema"], 2)

    def test_invalid_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            p.write_text("NOT JSON", encoding="utf-8")
            result = at.load_state(repo_root=td, state_path=p)
            self.assertEqual(result["sessions"], {})

    def test_non_dict_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            result = at.load_state(repo_root=td, state_path=p)
            self.assertEqual(result["sessions"], {})

    def test_returns_dict(self):
        result = at.load_state(repo_root="/no/path")
        self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# save_state
# ---------------------------------------------------------------------------

class TestSaveState(unittest.TestCase):
    """Tests for save_state() — writes JSON state file."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "state.json"
            at.save_state({"schema": 1}, repo_root=td, state_path=p)
            self.assertTrue(p.exists())

    def test_content_is_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            at.save_state({"schema": 1, "sessions": {"s": {}}}, repo_root=td, state_path=p)
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertIn("s", data["sessions"])

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            result = at.save_state({"schema": 1}, repo_root=td, state_path=p)
            self.assertIsInstance(result, Path)

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a" / "b" / "state.json"
            at.save_state({"schema": 1}, repo_root=td, state_path=p)
            self.assertTrue(p.parent.is_dir())


if __name__ == "__main__":
    unittest.main()
