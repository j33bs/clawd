"""Tests for workspace/memory/arousal_tracker.py pure helper functions.

Covers:
- _default_state
- _resolve_path
- _clamp
- _tone_to_energy
- load_state / save_state round-trip
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

from arousal_tracker import (  # noqa: E402
    _clamp,
    _default_state,
    _resolve_path,
    _tone_to_energy,
    load_state,
    save_state,
)


# ---------------------------------------------------------------------------
# _default_state
# ---------------------------------------------------------------------------

class TestDefaultState(unittest.TestCase):
    def test_returns_dict(self):
        self.assertIsInstance(_default_state(), dict)

    def test_schema_is_1(self):
        self.assertEqual(_default_state()["schema"], 1)

    def test_sessions_is_empty(self):
        self.assertEqual(_default_state()["sessions"], {})

    def test_each_call_new_instance(self):
        a = _default_state()
        b = _default_state()
        a["sessions"]["x"] = 1
        self.assertNotIn("x", b["sessions"])


# ---------------------------------------------------------------------------
# _resolve_path
# ---------------------------------------------------------------------------

class TestResolvePath(unittest.TestCase):
    def test_returns_path(self):
        self.assertIsInstance(_resolve_path("/tmp"), Path)

    def test_default_relative_to_root(self):
        result = _resolve_path("/root")
        self.assertTrue(str(result).startswith("/root"))

    def test_absolute_explicit_unchanged(self):
        explicit = Path("/absolute/state.json")
        self.assertEqual(_resolve_path("/root", state_path=explicit), explicit)

    def test_relative_joined_to_root(self):
        result = _resolve_path("/root", state_path=Path("custom/state.json"))
        self.assertEqual(result, Path("/root/custom/state.json"))


# ---------------------------------------------------------------------------
# _clamp
# ---------------------------------------------------------------------------

class TestClamp(unittest.TestCase):
    def test_below_lo_clamped(self):
        self.assertAlmostEqual(_clamp(-1.0, 0.0, 1.0), 0.0)

    def test_above_hi_clamped(self):
        self.assertAlmostEqual(_clamp(2.0, 0.0, 1.0), 1.0)

    def test_within_range_unchanged(self):
        self.assertAlmostEqual(_clamp(0.5, 0.0, 1.0), 0.5)

    def test_custom_range(self):
        self.assertAlmostEqual(_clamp(15.0, 10.0, 20.0), 15.0)
        self.assertAlmostEqual(_clamp(5.0, 10.0, 20.0), 10.0)
        self.assertAlmostEqual(_clamp(25.0, 10.0, 20.0), 20.0)


# ---------------------------------------------------------------------------
# _tone_to_energy
# ---------------------------------------------------------------------------

class TestToneToEnergy(unittest.TestCase):
    """Tests for _tone_to_energy() — tone label → energy float."""

    def test_high_tone_gives_high_energy(self):
        self.assertAlmostEqual(_tone_to_energy("high"), 0.85)

    def test_urgent_gives_high_energy(self):
        self.assertAlmostEqual(_tone_to_energy("urgent"), 0.85)

    def test_stressed_gives_high_energy(self):
        self.assertAlmostEqual(_tone_to_energy("stressed"), 0.85)

    def test_excited_gives_high_energy(self):
        self.assertAlmostEqual(_tone_to_energy("excited"), 0.85)

    def test_low_gives_low_energy(self):
        self.assertAlmostEqual(_tone_to_energy("low"), 0.30)

    def test_calm_gives_low_energy(self):
        self.assertAlmostEqual(_tone_to_energy("calm"), 0.30)

    def test_flat_gives_low_energy(self):
        self.assertAlmostEqual(_tone_to_energy("flat"), 0.30)

    def test_neutral_gives_mid_energy(self):
        self.assertAlmostEqual(_tone_to_energy("neutral"), 0.50)

    def test_none_gives_mid_energy(self):
        self.assertAlmostEqual(_tone_to_energy(None), 0.50)

    def test_empty_gives_mid_energy(self):
        self.assertAlmostEqual(_tone_to_energy(""), 0.50)

    def test_returns_float(self):
        self.assertIsInstance(_tone_to_energy("high"), float)


# ---------------------------------------------------------------------------
# load_state / save_state round-trip
# ---------------------------------------------------------------------------

class TestLoadSaveState(unittest.TestCase):
    def test_missing_file_returns_default(self):
        with tempfile.TemporaryDirectory() as td:
            state = load_state(repo_root=td)
            self.assertEqual(state["schema"], 1)

    def test_invalid_json_returns_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.json"
            path.write_text("NOT JSON", encoding="utf-8")
            state = load_state(repo_root=td, state_path=path)
            self.assertEqual(state["sessions"], {})

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            state = _default_state()
            state["sessions"]["sess1"] = {"arousal": 0.65}
            save_state(state, repo_root=td, state_path=path)
            loaded = load_state(repo_root=td, state_path=path)
            self.assertIn("sess1", loaded["sessions"])
            self.assertAlmostEqual(float(loaded["sessions"]["sess1"]["arousal"]), 0.65)

    def test_save_returns_path(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            result = save_state(_default_state(), repo_root=td, state_path=path)
            self.assertIsInstance(result, Path)


if __name__ == "__main__":
    unittest.main()
