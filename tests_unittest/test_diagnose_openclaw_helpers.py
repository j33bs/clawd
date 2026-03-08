"""Tests for workspace/scripts/diagnose_openclaw_status_hang.py pure helpers.

Covers (no subprocess execution):
- truncate
- diagnose
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from diagnose_openclaw_status_hang import (  # noqa: E402
    diagnose,
    truncate,
)


# ---------------------------------------------------------------------------
# truncate
# ---------------------------------------------------------------------------

class TestTruncate(unittest.TestCase):
    """Tests for truncate() — clips text at `size` chars and appends '...'."""

    def test_empty_returns_empty(self):
        self.assertEqual(truncate(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(truncate(None), "")

    def test_short_text_unchanged(self):
        self.assertEqual(truncate("hello", 10), "hello")

    def test_text_at_limit_unchanged(self):
        text = "x" * 300
        result = truncate(text, 300)
        self.assertEqual(result, text)

    def test_long_text_clipped(self):
        text = "x" * 400
        result = truncate(text, 300)
        self.assertLessEqual(len(result), 304)  # 300 + "..."

    def test_ellipsis_appended_when_truncated(self):
        text = "a" * 400
        result = truncate(text, 300)
        self.assertTrue(result.endswith("..."))

    def test_returns_string(self):
        self.assertIsInstance(truncate("text", 10), str)


# ---------------------------------------------------------------------------
# diagnose
# ---------------------------------------------------------------------------

class TestDiagnose(unittest.TestCase):
    """Tests for diagnose() — returns list of diagnostic notes."""

    def test_no_openclaw_returns_path_note(self):
        result = diagnose([], has_openclaw=False)
        self.assertTrue(any("not found" in note for note in result))

    def test_returns_list(self):
        result = diagnose([], has_openclaw=False)
        self.assertIsInstance(result, list)

    def test_both_timeouts_generates_note(self):
        results = [
            {"command": "openclaw status", "timed_out": True, "stdout": "", "stderr": ""},
            {"command": "openclaw status --deep", "timed_out": True, "stdout": "", "stderr": ""},
            {"command": "openclaw status --json", "timed_out": False, "exit_code": 0, "stdout": "", "stderr": ""},
        ]
        notes = diagnose(results, has_openclaw=True)
        self.assertTrue(any("timed out" in n for n in notes))

    def test_no_stdout_before_timeout_generates_note(self):
        results = [
            {"command": "openclaw status", "timed_out": True, "stdout": "", "stderr": ""},
        ]
        notes = diagnose(results, has_openclaw=True)
        self.assertTrue(any("blocked" in n or "No stdout" in n for n in notes))

    def test_unknown_json_flag_generates_note(self):
        results = [
            {"command": "openclaw status --json", "timed_out": False, "exit_code": 1, "stdout": "", "stderr": "unknown option"},
        ]
        notes = diagnose(results, has_openclaw=True)
        self.assertTrue(any("unsupported" in n for n in notes))

    def test_no_issues_returns_fallback_note(self):
        results = [
            {"command": "openclaw status", "timed_out": False, "exit_code": 0, "stdout": "ok", "stderr": ""},
        ]
        notes = diagnose(results, has_openclaw=True)
        # Falls back to "No single root cause"
        self.assertTrue(any("No single" in n or "inspect" in n for n in notes))


if __name__ == "__main__":
    unittest.main()
