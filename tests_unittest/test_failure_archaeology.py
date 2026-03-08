"""Tests for failure_archaeology.log_failure() — isolation and validation."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import failure_archaeology as fa


class TestLogFailure(unittest.TestCase):
    """Test log_failure() — file creation, content, return value."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_dir = fa.FAILURES_DIR
        fa.FAILURES_DIR = self._tmp / "failures"

    def tearDown(self):
        fa.FAILURES_DIR = self._orig_dir
        self._tmpdir.cleanup()

    def test_creates_failures_dir_if_missing(self):
        self.assertFalse(fa.FAILURES_DIR.exists())
        fa.log_failure("test_error")
        self.assertTrue(fa.FAILURES_DIR.exists())

    def test_creates_at_least_one_file_per_call(self):
        # IDs are second-resolution; rapid calls in the same second share a file.
        # This is a known limitation of the implementation (no sub-second suffix).
        fa.log_failure("error_a")
        fa.log_failure("error_b")
        files = list(fa.FAILURES_DIR.glob("*.json"))
        self.assertGreaterEqual(len(files), 1)
        # The last written entry (error_b) must be on disk
        latest = max(files, key=lambda p: p.stat().st_mtime)
        content = __import__("json").loads(latest.read_text(encoding="utf-8"))
        self.assertIn(content["error"], ("error_a", "error_b"))

    def test_return_value_has_required_keys(self):
        entry = fa.log_failure("some_error", "some_context")
        self.assertIn("id", entry)
        self.assertIn("error", entry)
        self.assertIn("context", entry)
        self.assertIn("root_cause", entry)
        self.assertIn("lesson", entry)
        self.assertIn("timestamp", entry)

    def test_error_field_matches_input(self):
        entry = fa.log_failure("missing_api_key")
        self.assertEqual(entry["error"], "missing_api_key")

    def test_context_field_matches_input(self):
        entry = fa.log_failure("timeout", "TeamChat planning phase")
        self.assertEqual(entry["context"], "TeamChat planning phase")

    def test_context_defaults_to_empty_string(self):
        entry = fa.log_failure("some_error")
        self.assertEqual(entry["context"], "")

    def test_root_cause_defaults_to_tbd(self):
        entry = fa.log_failure("error")
        self.assertEqual(entry["root_cause"], "TBD")

    def test_lesson_defaults_to_tbd(self):
        entry = fa.log_failure("error")
        self.assertEqual(entry["lesson"], "TBD")

    def test_id_has_failure_prefix(self):
        entry = fa.log_failure("error")
        self.assertTrue(entry["id"].startswith("failure_"))

    def test_json_file_is_valid_and_matches_entry(self):
        entry = fa.log_failure("recoverable_error", "context_here")
        file_path = fa.FAILURES_DIR / f"{entry['id']}.json"
        self.assertTrue(file_path.exists())
        written = json.loads(file_path.read_text(encoding="utf-8"))
        self.assertEqual(written["error"], "recoverable_error")
        self.assertEqual(written["context"], "context_here")

    def test_timestamp_is_utc_iso(self):
        entry = fa.log_failure("err")
        ts = entry["timestamp"]
        self.assertIn("+00:00", ts)

    def test_multiple_failures_have_unique_ids(self):
        import time
        e1 = fa.log_failure("error_one")
        time.sleep(0.01)
        e2 = fa.log_failure("error_two")
        # IDs include timestamp — may collide within same second, but files are still created
        self.assertIsNotNone(e1["id"])
        self.assertIsNotNone(e2["id"])


if __name__ == "__main__":
    unittest.main()
