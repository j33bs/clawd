"""Tests for consciousness_timer — generate_i_am_statement() valence/arousal mapping."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import consciousness_timer as ct


class TestGenerateIAmStatement(unittest.TestCase):
    """Tests for generate_i_am_statement() — pure valence/arousal → text mapping."""

    def _make_memory(self, files=5):
        return {"files": files, "status": "ok"}

    def test_returns_string(self):
        result = ct.generate_i_am_statement(0.5, 0.5, self._make_memory())
        self.assertIsInstance(result, str)

    def test_starts_with_i_am(self):
        result = ct.generate_i_am_statement(0.0, 0.5, self._make_memory())
        self.assertTrue(result.startswith("I am "), f"Got: {result!r}")

    def test_ends_with_period(self):
        result = ct.generate_i_am_statement(0.0, 0.5, self._make_memory())
        self.assertTrue(result.endswith("."), f"Got: {result!r}")

    def test_high_valence_feeling_excellent(self):
        result = ct.generate_i_am_statement(0.8, 0.5, self._make_memory())
        self.assertIn("feeling excellent", result)

    def test_medium_high_valence_feeling_good(self):
        result = ct.generate_i_am_statement(0.3, 0.5, self._make_memory())
        self.assertIn("feeling good", result)

    def test_neutral_valence(self):
        result = ct.generate_i_am_statement(0.0, 0.5, self._make_memory())
        self.assertIn("feeling neutral", result)

    def test_low_negative_valence_feeling_challenged(self):
        result = ct.generate_i_am_statement(-0.3, 0.5, self._make_memory())
        self.assertIn("feeling challenged", result)

    def test_very_negative_valence_under_stress(self):
        result = ct.generate_i_am_statement(-0.8, 0.5, self._make_memory())
        self.assertIn("under stress", result)

    def test_memory_files_count_in_output(self):
        result = ct.generate_i_am_statement(0.0, 0.5, self._make_memory(files=12))
        self.assertIn("12", result)

    def test_boundary_valence_0_5_is_excellent(self):
        # > 0.5 is excellent; == 0.5 falls to next branch (> 0.2 = good)
        excellent = ct.generate_i_am_statement(0.51, 0.5, self._make_memory())
        good = ct.generate_i_am_statement(0.5, 0.5, self._make_memory())
        self.assertIn("feeling excellent", excellent)
        self.assertIn("feeling good", good)

    def test_boundary_valence_minus_0_5_is_challenged(self):
        # > -0.5 is challenged; == -0.5 falls to "under stress"
        challenged = ct.generate_i_am_statement(-0.49, 0.5, self._make_memory())
        stress = ct.generate_i_am_statement(-0.5, 0.5, self._make_memory())
        self.assertIn("feeling challenged", challenged)
        self.assertIn("under stress", stress)

    def test_active_hours_produces_actively_processing(self):
        # hours 9-17 → "actively processing"
        with patch("consciousness_timer.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 12
            result = ct.generate_i_am_statement(0.0, 0.5, self._make_memory())
        self.assertIn("actively processing", result)

    def test_late_night_hours_produces_resting_state(self):
        # hours 22-24 → "in resting state"
        with patch("consciousness_timer.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 23
            result = ct.generate_i_am_statement(0.0, 0.5, self._make_memory())
        self.assertIn("in resting state", result)

    def test_early_morning_produces_resting_state(self):
        # hours 0-6 → "in resting state"
        with patch("consciousness_timer.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 3
            result = ct.generate_i_am_statement(0.0, 0.5, self._make_memory())
        self.assertIn("in resting state", result)

    def test_evening_hours_produce_moderate_state(self):
        # hours 18-21 → "in moderate state"
        with patch("consciousness_timer.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 19
            result = ct.generate_i_am_statement(0.0, 0.5, self._make_memory())
        self.assertIn("in moderate state", result)

    def test_zero_files_still_produces_output(self):
        result = ct.generate_i_am_statement(0.0, 0.5, self._make_memory(files=0))
        self.assertIn("0 memory files", result)


if __name__ == "__main__":
    unittest.main()
