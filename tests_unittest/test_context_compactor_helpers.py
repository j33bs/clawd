"""Tests for pure helpers in workspace/memory/context_compactor.py.

Pure stdlib (json, pathlib, datetime) — no stubs needed.
Uses tempfile for filesystem isolation.

Covers:
- ContextCompactor.should_compact
- ContextCompactor.compact
- ContextCompactor.auto_check
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPACTOR_PATH = REPO_ROOT / "workspace" / "memory" / "context_compactor.py"

_spec = _ilu.spec_from_file_location("context_compactor_real", str(COMPACTOR_PATH))
cc = _ilu.module_from_spec(_spec)
sys.modules["context_compactor_real"] = cc
_spec.loader.exec_module(cc)


def _make_compactor(tmp: str, avg_tokens: float | None = None) -> "cc.ContextCompactor":
    """Create a ContextCompactor backed by a temp arousal_state.json."""
    p = Path(tmp) / "arousal_state.json"
    if avg_tokens is not None:
        payload = {"metrics": {"avg_tokens_per_message": avg_tokens}}
        p.write_text(json.dumps(payload), encoding="utf-8")
    return cc.ContextCompactor(arousal_tracker_path=str(p))


# ---------------------------------------------------------------------------
# should_compact
# ---------------------------------------------------------------------------

class TestShouldCompact(unittest.TestCase):
    """Tests for ContextCompactor.should_compact() — threshold check."""

    def test_returns_false_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            compactor = _make_compactor(tmp)  # no avg_tokens written
            self.assertFalse(compactor.should_compact())

    def test_returns_false_below_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            compactor = _make_compactor(tmp, avg_tokens=5000.0)
            self.assertFalse(compactor.should_compact())

    def test_returns_true_above_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            compactor = _make_compactor(tmp, avg_tokens=9000.0)
            self.assertTrue(compactor.should_compact())

    def test_returns_false_exactly_at_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            compactor = _make_compactor(tmp, avg_tokens=8000.0)
            # 8000 > 8000 is False
            self.assertFalse(compactor.should_compact())

    def test_returns_bool(self):
        with tempfile.TemporaryDirectory() as tmp:
            compactor = _make_compactor(tmp)
            result = compactor.should_compact()
            self.assertIsInstance(result, bool)


# ---------------------------------------------------------------------------
# compact
# ---------------------------------------------------------------------------

class TestCompact(unittest.TestCase):
    """Tests for ContextCompactor.compact() — keep head+tail, summarize middle."""

    def _make_compactor(self):
        return cc.ContextCompactor(arousal_tracker_path="/tmp/nonexistent")

    def test_empty_context_returns_empty(self):
        compactor = self._make_compactor()
        result, summary = compactor.compact("")
        self.assertEqual(result, "")
        self.assertIn("No context", summary)

    def test_short_context_unchanged(self):
        compactor = self._make_compactor()
        short = "\n".join(f"line {i}" for i in range(10))
        result, summary = compactor.compact(short)
        self.assertEqual(result, short)
        self.assertIn("too small", summary)

    def test_long_context_compacted(self):
        compactor = self._make_compactor()
        long_ctx = "\n".join(f"line {i}" for i in range(50))
        result, summary = compactor.compact(long_ctx)
        self.assertIn("[compacted]", result)

    def test_compacted_shorter_than_original(self):
        compactor = self._make_compactor()
        long_ctx = "\n".join(f"line {i}" for i in range(50))
        result, summary = compactor.compact(long_ctx)
        self.assertLess(len(result), len(long_ctx))

    def test_returns_tuple(self):
        compactor = self._make_compactor()
        result = compactor.compact("test")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_summary_is_string(self):
        compactor = self._make_compactor()
        _, summary = compactor.compact("test")
        self.assertIsInstance(summary, str)

    def test_keeps_first_and_last_lines(self):
        compactor = self._make_compactor()
        lines = [f"line_{i}" for i in range(30)]
        context = "\n".join(lines)
        result, _ = compactor.compact(context)
        # First line and last line should appear
        self.assertIn("line_0", result)
        self.assertIn("line_29", result)


# ---------------------------------------------------------------------------
# auto_check
# ---------------------------------------------------------------------------

class TestAutoCheck(unittest.TestCase):
    """Tests for ContextCompactor.auto_check() — combined check+compact."""

    def test_returns_tuple_of_three(self):
        with tempfile.TemporaryDirectory() as tmp:
            compactor = _make_compactor(tmp)
            result = compactor.auto_check()
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 3)

    def test_healthy_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            compactor = _make_compactor(tmp, avg_tokens=1000.0)
            should, context, msg = compactor.auto_check()
            self.assertFalse(should)

    def test_healthy_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            compactor = _make_compactor(tmp)
            should, context, msg = compactor.auto_check()
            self.assertIn("healthy", msg)

    def test_high_arousal_no_context_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            compactor = _make_compactor(tmp, avg_tokens=9000.0)
            should, context, msg = compactor.auto_check()
            self.assertTrue(should)
            self.assertIsNone(context)

    def test_high_arousal_with_long_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            compactor = _make_compactor(tmp, avg_tokens=9000.0)
            long_ctx = "\n".join(f"line {i}" for i in range(50))
            should, compacted, msg = compactor.auto_check(long_ctx)
            self.assertTrue(should)
            self.assertIsNotNone(compacted)


if __name__ == "__main__":
    unittest.main()
