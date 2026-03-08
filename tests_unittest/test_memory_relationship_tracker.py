"""Tests for workspace/memory/relationship_tracker.py pure helper functions.

Covers:
- _default_state
- _tone_adjustment
- _clamp
- _resolve_path
- load_state (missing/invalid/valid files)
- save_state (round-trip)
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = REPO_ROOT / "workspace" / "memory"
if str(MEMORY_DIR) not in sys.path:
    sys.path.insert(0, str(MEMORY_DIR))

from relationship_tracker import (  # noqa: E402
    _clamp,
    _default_state,
    _resolve_path,
    _tone_adjustment,
    load_state,
    save_state,
)


# ---------------------------------------------------------------------------
# _default_state
# ---------------------------------------------------------------------------

class TestDefaultState(unittest.TestCase):
    """Tests for _default_state() — canonical empty structure."""

    def test_returns_dict(self):
        self.assertIsInstance(_default_state(), dict)

    def test_has_schema_key(self):
        self.assertIn("schema", _default_state())

    def test_has_sessions_key(self):
        self.assertIn("sessions", _default_state())

    def test_sessions_is_empty_dict(self):
        self.assertEqual(_default_state()["sessions"], {})

    def test_schema_is_1(self):
        self.assertEqual(_default_state()["schema"], 1)

    def test_returns_new_instance_each_call(self):
        a = _default_state()
        b = _default_state()
        a["sessions"]["x"] = 1
        self.assertNotIn("x", b["sessions"])


# ---------------------------------------------------------------------------
# _tone_adjustment
# ---------------------------------------------------------------------------

class TestToneAdjustment(unittest.TestCase):
    """Tests for _tone_adjustment() — tone label → float delta."""

    def test_supportive_positive(self):
        self.assertGreater(_tone_adjustment("supportive"), 0.0)

    def test_warm_positive(self):
        self.assertGreater(_tone_adjustment("warm"), 0.0)

    def test_calm_positive(self):
        self.assertGreater(_tone_adjustment("calm"), 0.0)

    def test_positive_label_positive(self):
        self.assertGreater(_tone_adjustment("positive"), 0.0)

    def test_hostile_negative(self):
        self.assertLess(_tone_adjustment("hostile"), 0.0)

    def test_frustrated_negative(self):
        self.assertLess(_tone_adjustment("frustrated"), 0.0)

    def test_negative_label_negative(self):
        self.assertLess(_tone_adjustment("negative"), 0.0)

    def test_neutral_returns_zero(self):
        self.assertAlmostEqual(_tone_adjustment("neutral"), 0.0)

    def test_empty_returns_zero(self):
        self.assertAlmostEqual(_tone_adjustment(""), 0.0)

    def test_unknown_label_returns_zero(self):
        self.assertAlmostEqual(_tone_adjustment("purple"), 0.0)

    def test_returns_float(self):
        self.assertIsInstance(_tone_adjustment("warm"), float)


# ---------------------------------------------------------------------------
# _clamp
# ---------------------------------------------------------------------------

class TestClamp(unittest.TestCase):
    """Tests for _clamp(value, lo, hi) — generic range clamp."""

    def test_below_lo_clamped(self):
        self.assertAlmostEqual(_clamp(-5.0, 0.0, 1.0), 0.0)

    def test_above_hi_clamped(self):
        self.assertAlmostEqual(_clamp(2.0, 0.0, 1.0), 1.0)

    def test_within_range_unchanged(self):
        self.assertAlmostEqual(_clamp(0.5, 0.0, 1.0), 0.5)

    def test_at_lo_boundary(self):
        self.assertAlmostEqual(_clamp(0.0, 0.0, 1.0), 0.0)

    def test_at_hi_boundary(self):
        self.assertAlmostEqual(_clamp(1.0, 0.0, 1.0), 1.0)

    def test_custom_range(self):
        self.assertAlmostEqual(_clamp(15.0, 10.0, 20.0), 15.0)
        self.assertAlmostEqual(_clamp(5.0, 10.0, 20.0), 10.0)
        self.assertAlmostEqual(_clamp(25.0, 10.0, 20.0), 20.0)


# ---------------------------------------------------------------------------
# _resolve_path
# ---------------------------------------------------------------------------

class TestResolvePath(unittest.TestCase):
    """Tests for _resolve_path() — root-relative or absolute path resolution."""

    def test_returns_path(self):
        self.assertIsInstance(_resolve_path("/tmp"), Path)

    def test_default_path_relative_to_root(self):
        result = _resolve_path("/some/root")
        self.assertTrue(str(result).startswith("/some/root"))

    def test_explicit_absolute_path_unchanged(self):
        explicit = Path("/absolute/custom/state.json")
        result = _resolve_path("/some/root", state_path=explicit)
        self.assertEqual(result, explicit)

    def test_explicit_relative_path_joined_to_root(self):
        result = _resolve_path("/root", state_path=Path("custom/state.json"))
        self.assertEqual(result, Path("/root/custom/state.json"))


# ---------------------------------------------------------------------------
# load_state / save_state
# ---------------------------------------------------------------------------

class TestLoadState(unittest.TestCase):
    """Tests for load_state() — reads from file or returns defaults."""

    def test_missing_file_returns_default(self):
        with tempfile.TemporaryDirectory() as td:
            state = load_state(repo_root=td)
            self.assertEqual(state["schema"], 1)
            self.assertEqual(state["sessions"], {})

    def test_valid_file_loaded(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "workspace" / "state_runtime" / "memory" / "relationship_state.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"schema": 1, "updated_at": "2026-01-01", "sessions": {"s1": {}}}),
                encoding="utf-8",
            )
            state = load_state(repo_root=td, state_path=path)
            self.assertIn("s1", state["sessions"])

    def test_invalid_json_returns_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.json"
            path.write_text("NOT JSON", encoding="utf-8")
            state = load_state(repo_root=td, state_path=path)
            self.assertEqual(state["sessions"], {})

    def test_non_dict_json_returns_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.json"
            path.write_text('["list"]', encoding="utf-8")
            state = load_state(repo_root=td, state_path=path)
            self.assertEqual(state["sessions"], {})


class TestSaveState(unittest.TestCase):
    """Tests for save_state() — persists state to file."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sub" / "state.json"
            state = _default_state()
            save_state(state, repo_root=td, state_path=path)
            self.assertTrue(path.exists())

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            state = _default_state()
            state["sessions"]["test_session"] = {"trust_score": 0.75}
            save_state(state, repo_root=td, state_path=path)
            loaded = load_state(repo_root=td, state_path=path)
            self.assertIn("test_session", loaded["sessions"])
            self.assertAlmostEqual(
                float(loaded["sessions"]["test_session"]["trust_score"]), 0.75
            )

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            result = save_state(_default_state(), repo_root=td, state_path=path)
            self.assertIsInstance(result, Path)


if __name__ == "__main__":
    unittest.main()
