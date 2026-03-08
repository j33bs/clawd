"""Tests for pure helpers in workspace/local_exec/budgets.py.

Pure stdlib (time, dataclasses, pathlib) — no stubs needed.

Covers:
- BudgetLimits dataclass
- BudgetTracker.elapsed_sec
- BudgetTracker.check_wall_time
- BudgetTracker.record_tool_call
- BudgetTracker.record_output_bytes
- kill_switch_path
- kill_switch_enabled
"""
import importlib.util as _ilu
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUDGETS_PATH = REPO_ROOT / "workspace" / "local_exec" / "budgets.py"

_spec = _ilu.spec_from_file_location("local_exec_budgets_real", str(BUDGETS_PATH))
bud = _ilu.module_from_spec(_spec)
sys.modules["local_exec_budgets_real"] = bud
_spec.loader.exec_module(bud)


# ---------------------------------------------------------------------------
# BudgetLimits
# ---------------------------------------------------------------------------

class TestBudgetLimits(unittest.TestCase):
    """Tests for BudgetLimits dataclass — simple field storage."""

    def _make(self, **kw):
        defaults = dict(max_wall_time_sec=60, max_tool_calls=10,
                        max_output_bytes=4096, max_concurrency_slots=2)
        defaults.update(kw)
        return bud.BudgetLimits(**defaults)

    def test_fields_stored(self):
        bl = self._make(max_wall_time_sec=120)
        self.assertEqual(bl.max_wall_time_sec, 120)

    def test_max_tool_calls(self):
        bl = self._make(max_tool_calls=5)
        self.assertEqual(bl.max_tool_calls, 5)

    def test_max_output_bytes(self):
        bl = self._make(max_output_bytes=8192)
        self.assertEqual(bl.max_output_bytes, 8192)

    def test_max_concurrency_slots(self):
        bl = self._make(max_concurrency_slots=4)
        self.assertEqual(bl.max_concurrency_slots, 4)


# ---------------------------------------------------------------------------
# BudgetTracker.elapsed_sec
# ---------------------------------------------------------------------------

class TestBudgetTrackerElapsed(unittest.TestCase):
    """Tests for BudgetTracker.elapsed_sec()."""

    def _make_tracker(self, wall=60, calls=10, out=4096, slots=2):
        limits = bud.BudgetLimits(
            max_wall_time_sec=wall, max_tool_calls=calls,
            max_output_bytes=out, max_concurrency_slots=slots,
        )
        return bud.BudgetTracker(limits)

    def test_returns_float(self):
        tracker = self._make_tracker()
        self.assertIsInstance(tracker.elapsed_sec(), float)

    def test_initially_small(self):
        tracker = self._make_tracker()
        self.assertLess(tracker.elapsed_sec(), 2.0)

    def test_increases_over_time(self):
        tracker = self._make_tracker()
        t0 = tracker.elapsed_sec()
        time.sleep(0.05)
        t1 = tracker.elapsed_sec()
        self.assertGreater(t1, t0)


# ---------------------------------------------------------------------------
# BudgetTracker.check_wall_time
# ---------------------------------------------------------------------------

class TestBudgetTrackerCheckWallTime(unittest.TestCase):
    """Tests for BudgetTracker.check_wall_time()."""

    def _make_tracker(self, wall=60):
        limits = bud.BudgetLimits(
            max_wall_time_sec=wall, max_tool_calls=100,
            max_output_bytes=1048576, max_concurrency_slots=2,
        )
        return bud.BudgetTracker(limits)

    def test_does_not_raise_when_under_limit(self):
        tracker = self._make_tracker(wall=3600)
        tracker.check_wall_time()  # should not raise

    def test_raises_budget_exceeded_when_over_limit(self):
        limits = bud.BudgetLimits(
            max_wall_time_sec=0, max_tool_calls=100,
            max_output_bytes=1048576, max_concurrency_slots=2,
        )
        tracker = bud.BudgetTracker(limits)
        time.sleep(0.01)
        with self.assertRaises(bud.BudgetExceeded):
            tracker.check_wall_time()

    def test_raises_correct_exception_type(self):
        limits = bud.BudgetLimits(
            max_wall_time_sec=0, max_tool_calls=100,
            max_output_bytes=1048576, max_concurrency_slots=2,
        )
        tracker = bud.BudgetTracker(limits)
        time.sleep(0.01)
        with self.assertRaises(RuntimeError):
            tracker.check_wall_time()


# ---------------------------------------------------------------------------
# BudgetTracker.record_tool_call
# ---------------------------------------------------------------------------

class TestBudgetTrackerRecordToolCall(unittest.TestCase):
    """Tests for BudgetTracker.record_tool_call()."""

    def _make_tracker(self, max_calls=5):
        limits = bud.BudgetLimits(
            max_wall_time_sec=3600, max_tool_calls=max_calls,
            max_output_bytes=1048576, max_concurrency_slots=2,
        )
        return bud.BudgetTracker(limits)

    def test_increments_count(self):
        tracker = self._make_tracker(max_calls=10)
        tracker.record_tool_call()
        self.assertEqual(tracker.tool_calls, 1)

    def test_multiple_calls_accumulate(self):
        tracker = self._make_tracker(max_calls=10)
        tracker.record_tool_call(3)
        self.assertEqual(tracker.tool_calls, 3)

    def test_raises_at_limit(self):
        tracker = self._make_tracker(max_calls=2)
        tracker.record_tool_call()
        tracker.record_tool_call()
        with self.assertRaises(bud.BudgetExceeded):
            tracker.record_tool_call()

    def test_no_raise_at_limit_exactly(self):
        tracker = self._make_tracker(max_calls=3)
        tracker.record_tool_call()
        tracker.record_tool_call()
        tracker.record_tool_call()  # at limit, not over — implementation raises when > limit
        # The check is > not >= so this should raise after 3 if limit is 3
        # Actually tool_calls > limits.max_tool_calls means 4 > 3 raises
        # So 3 calls when limit=3 should NOT raise (3 > 3 is False)
        pass  # no assertion — just verify no error

    def test_initial_count_zero(self):
        tracker = self._make_tracker()
        self.assertEqual(tracker.tool_calls, 0)


# ---------------------------------------------------------------------------
# BudgetTracker.record_output_bytes
# ---------------------------------------------------------------------------

class TestBudgetTrackerRecordOutputBytes(unittest.TestCase):
    """Tests for BudgetTracker.record_output_bytes()."""

    def _make_tracker(self, max_bytes=1000):
        limits = bud.BudgetLimits(
            max_wall_time_sec=3600, max_tool_calls=100,
            max_output_bytes=max_bytes, max_concurrency_slots=2,
        )
        return bud.BudgetTracker(limits)

    def test_increments_bytes(self):
        tracker = self._make_tracker(max_bytes=10000)
        tracker.record_output_bytes(500)
        self.assertEqual(tracker.output_bytes, 500)

    def test_accumulates(self):
        tracker = self._make_tracker(max_bytes=10000)
        tracker.record_output_bytes(200)
        tracker.record_output_bytes(300)
        self.assertEqual(tracker.output_bytes, 500)

    def test_raises_when_over_limit(self):
        tracker = self._make_tracker(max_bytes=100)
        with self.assertRaises(bud.BudgetExceeded):
            tracker.record_output_bytes(200)

    def test_initial_bytes_zero(self):
        tracker = self._make_tracker()
        self.assertEqual(tracker.output_bytes, 0)


# ---------------------------------------------------------------------------
# kill_switch_path
# ---------------------------------------------------------------------------

class TestKillSwitchPath(unittest.TestCase):
    """Tests for kill_switch_path() — pure path calculation."""

    def test_returns_path(self):
        result = bud.kill_switch_path(Path("/tmp/fakerepo"))
        self.assertIsInstance(result, Path)

    def test_contains_kill_switch(self):
        result = bud.kill_switch_path(Path("/tmp/fakerepo"))
        self.assertEqual(result.name, "KILL_SWITCH")

    def test_under_workspace_local_exec_state(self):
        result = bud.kill_switch_path(Path("/tmp/fakerepo"))
        parts = result.parts
        self.assertIn("workspace", parts)
        self.assertIn("local_exec", parts)
        self.assertIn("state", parts)


# ---------------------------------------------------------------------------
# kill_switch_enabled
# ---------------------------------------------------------------------------

class TestKillSwitchEnabled(unittest.TestCase):
    """Tests for kill_switch_enabled() — checks file existence."""

    def test_false_when_file_absent(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            result = bud.kill_switch_enabled(Path(tmp))
            self.assertFalse(result)

    def test_true_when_file_present(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ks = bud.kill_switch_path(Path(tmp))
            ks.parent.mkdir(parents=True, exist_ok=True)
            ks.touch()
            self.assertTrue(bud.kill_switch_enabled(Path(tmp)))

    def test_returns_bool(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = bud.kill_switch_enabled(Path(tmp))
            self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
