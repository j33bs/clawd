"""Tests for phenomenal_binding — bind_experience() file creation and content."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import phenomenal_binding as pb


class TestBindExperience(unittest.TestCase):
    """Tests for bind_experience() — entry creation and persistence."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_binding_log = pb.BINDING_LOG
        pb.BINDING_LOG = self._tmp / "phenomenal" / "binding_log.jsonl"

    def tearDown(self):
        pb.BINDING_LOG = self._orig_binding_log
        self._tmpdir.cleanup()

    def test_creates_parent_dir(self):
        self.assertFalse(pb.BINDING_LOG.parent.exists())
        pb.bind_experience("saw", "thought", "acted")
        self.assertTrue(pb.BINDING_LOG.parent.exists())

    def test_creates_log_file(self):
        pb.bind_experience("perceived input", "analyzed it", "produced output")
        self.assertTrue(pb.BINDING_LOG.exists())

    def test_return_value_has_required_keys(self):
        entry = pb.bind_experience("perception", "reasoning", "action")
        self.assertIn("timestamp", entry)
        self.assertIn("perception", entry)
        self.assertIn("reasoning", entry)
        self.assertIn("action", entry)
        self.assertIn("narrative", entry)

    def test_perception_field_matches_input(self):
        entry = pb.bind_experience("saw a user message", "considered it", "responded")
        self.assertEqual(entry["perception"], "saw a user message")

    def test_reasoning_field_matches_input(self):
        entry = pb.bind_experience("saw", "deduced the intent", "responded")
        self.assertEqual(entry["reasoning"], "deduced the intent")

    def test_action_field_matches_input(self):
        entry = pb.bind_experience("saw", "thought", "wrote the code")
        self.assertEqual(entry["action"], "wrote the code")

    def test_narrative_contains_all_parts(self):
        entry = pb.bind_experience("P", "R", "A")
        self.assertIn("P", entry["narrative"])
        self.assertIn("R", entry["narrative"])
        self.assertIn("A", entry["narrative"])

    def test_narrative_format(self):
        entry = pb.bind_experience("read input", "planned approach", "executed solution")
        self.assertIn("I read input", entry["narrative"])
        self.assertIn("I thought: planned approach", entry["narrative"])
        self.assertIn("I executed solution", entry["narrative"])

    def test_timestamp_is_string(self):
        entry = pb.bind_experience("p", "r", "a")
        self.assertIsInstance(entry["timestamp"], str)
        self.assertGreater(len(entry["timestamp"]), 0)

    def test_log_file_contains_valid_json(self):
        pb.bind_experience("saw x", "thought y", "did z")
        line = pb.BINDING_LOG.read_text(encoding="utf-8").strip()
        parsed = json.loads(line)
        self.assertEqual(parsed["perception"], "saw x")

    def test_multiple_calls_append_entries(self):
        pb.bind_experience("p1", "r1", "a1")
        pb.bind_experience("p2", "r2", "a2")
        lines = pb.BINDING_LOG.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        entry1 = json.loads(lines[0])
        entry2 = json.loads(lines[1])
        self.assertEqual(entry1["perception"], "p1")
        self.assertEqual(entry2["perception"], "p2")

    def test_each_entry_on_its_own_line(self):
        pb.bind_experience("x", "y", "z")
        content = pb.BINDING_LOG.read_text(encoding="utf-8")
        self.assertTrue(content.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
