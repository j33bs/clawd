"""Tests for metacognitive_loop — log_thinking, before_action, recent_thoughts, what_am_i_doing."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import metacognitive_loop as mcl


class TestLogThinking(unittest.TestCase):
    """Tests for log_thinking() — write path."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_log = mcl.METACOG_LOG
        mcl.METACOG_LOG = self._tmp / "metacognition" / "thinking_log.jsonl"

    def tearDown(self):
        mcl.METACOG_LOG = self._orig_log
        self._tmpdir.cleanup()

    def test_creates_parent_dirs(self):
        self.assertFalse(mcl.METACOG_LOG.parent.exists())
        mcl.log_thinking("topic", "reason")
        self.assertTrue(mcl.METACOG_LOG.parent.exists())

    def test_creates_log_file(self):
        self.assertFalse(mcl.METACOG_LOG.exists())
        mcl.log_thinking("topic", "reason")
        self.assertTrue(mcl.METACOG_LOG.exists())

    def test_return_value_has_required_keys(self):
        entry = mcl.log_thinking("about_something", "because_reasons", "do_this_plan")
        self.assertIn("timestamp", entry)
        self.assertIn("about", entry)
        self.assertIn("reason", entry)
        self.assertIn("plan", entry)
        self.assertIn("type", entry)

    def test_about_field_matches_input(self):
        entry = mcl.log_thinking("processing_request", "user asked")
        self.assertEqual(entry["about"], "processing_request")

    def test_reason_field_matches_input(self):
        entry = mcl.log_thinking("topic", "for_science")
        self.assertEqual(entry["reason"], "for_science")

    def test_plan_field_is_none_by_default(self):
        entry = mcl.log_thinking("topic", "reason")
        self.assertIsNone(entry["plan"])

    def test_plan_field_set_when_provided(self):
        entry = mcl.log_thinking("topic", "reason", "my_plan")
        self.assertEqual(entry["plan"], "my_plan")

    def test_type_is_thinking(self):
        entry = mcl.log_thinking("x", "y")
        self.assertEqual(entry["type"], "thinking")

    def test_appends_multiple_entries(self):
        mcl.log_thinking("a", "b")
        mcl.log_thinking("c", "d")
        lines = [ln for ln in mcl.METACOG_LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertEqual(len(lines), 2)

    def test_each_line_is_valid_json(self):
        mcl.log_thinking("first", "r1")
        mcl.log_thinking("second", "r2")
        for line in mcl.METACOG_LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                parsed = json.loads(line)
                self.assertIn("about", parsed)


class TestBeforeAction(unittest.TestCase):
    """Tests for before_action() convenience wrapper."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_log = mcl.METACOG_LOG
        mcl.METACOG_LOG = self._tmp / "thinking_log.jsonl"

    def tearDown(self):
        mcl.METACOG_LOG = self._orig_log
        self._tmpdir.cleanup()

    def test_about_includes_action_text(self):
        entry = mcl.before_action("run_tests")
        self.assertIn("run_tests", entry["about"])

    def test_context_included_in_reason(self):
        entry = mcl.before_action("run_tests", "CI step")
        self.assertIn("CI step", entry["reason"])

    def test_no_context_defaults_to_user_requested(self):
        entry = mcl.before_action("do_something")
        self.assertIn("User requested", entry["reason"])


class TestRecentThoughts(unittest.TestCase):
    """Tests for recent_thoughts() — read path."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_log = mcl.METACOG_LOG
        mcl.METACOG_LOG = self._tmp / "thinking_log.jsonl"

    def tearDown(self):
        mcl.METACOG_LOG = self._orig_log
        self._tmpdir.cleanup()

    def test_returns_empty_list_when_log_missing(self):
        self.assertFalse(mcl.METACOG_LOG.exists())
        result = mcl.recent_thoughts()
        self.assertEqual(result, [])

    def test_returns_last_n_entries(self):
        for i in range(10):
            mcl.log_thinking(f"topic_{i}", f"reason_{i}")
        thoughts = mcl.recent_thoughts(3)
        self.assertEqual(len(thoughts), 3)
        self.assertEqual(thoughts[-1]["about"], "topic_9")

    def test_default_count_is_five(self):
        for i in range(8):
            mcl.log_thinking(f"t{i}", f"r{i}")
        thoughts = mcl.recent_thoughts()
        self.assertEqual(len(thoughts), 5)

    def test_each_thought_is_dict(self):
        mcl.log_thinking("a", "b")
        thoughts = mcl.recent_thoughts(1)
        self.assertIsInstance(thoughts[0], dict)

    def test_round_trip_preserves_content(self):
        mcl.log_thinking("my_topic", "my_reason", "my_plan")
        thoughts = mcl.recent_thoughts(1)
        self.assertEqual(thoughts[0]["about"], "my_topic")
        self.assertEqual(thoughts[0]["reason"], "my_reason")
        self.assertEqual(thoughts[0]["plan"], "my_plan")


class TestWhatAmIDoing(unittest.TestCase):
    """Tests for what_am_i_doing() — summary output."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_log = mcl.METACOG_LOG
        mcl.METACOG_LOG = self._tmp / "thinking_log.jsonl"

    def tearDown(self):
        mcl.METACOG_LOG = self._orig_log
        self._tmpdir.cleanup()

    def test_returns_default_when_no_thoughts(self):
        result = mcl.what_am_i_doing()
        self.assertIn("haven't been thinking", result)

    def test_returns_summary_with_thoughts(self):
        mcl.log_thinking("writing_tests", "test coverage")
        result = mcl.what_am_i_doing()
        self.assertIn("writing_tests", result)

    def test_summary_is_string(self):
        mcl.log_thinking("a", "b")
        result = mcl.what_am_i_doing()
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
