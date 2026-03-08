"""Tests for sleep_consolidation_prototype — _select_memory_files, _utc_now, write_outputs."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
HIVEMIND_DIR = REPO_ROOT / "workspace" / "hivemind"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(HIVEMIND_DIR) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_DIR))

import sleep_consolidation_prototype as scp


class TestUtcNow(unittest.TestCase):
    """Tests for _utc_now() — ISO timestamp with Z suffix."""

    def test_returns_string(self):
        self.assertIsInstance(scp._utc_now(), str)

    def test_ends_with_z(self):
        stamp = scp._utc_now()
        self.assertTrue(stamp.endswith("Z"), f"Expected Z suffix: {stamp!r}")

    def test_contains_t_separator(self):
        stamp = scp._utc_now()
        self.assertIn("T", stamp)

    def test_no_microseconds(self):
        stamp = scp._utc_now()
        time_part = stamp.split("T")[1].rstrip("Z")
        self.assertNotIn(".", time_part)

    def test_looks_like_iso(self):
        stamp = scp._utc_now()
        self.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestSelectMemoryFiles(unittest.TestCase):
    """Tests for _select_memory_files() — mtime-filtered .md file selection."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _create_md(self, name: str, age_hours: float = 0.0) -> Path:
        path = self._tmp / name
        path.write_text(f"# {name}", encoding="utf-8")
        if age_hours > 0:
            # Set mtime to age_hours in the past
            past = time.time() - age_hours * 3600
            os.utime(path, (past, past))
        return path

    def test_empty_dir_returns_empty(self):
        result = scp._select_memory_files(self._tmp, last_n=5, window_hours=24)
        self.assertEqual(result, [])

    def test_recent_files_included(self):
        self._create_md("recent.md", age_hours=1)  # 1 hour old
        result = scp._select_memory_files(self._tmp, last_n=10, window_hours=24)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "recent.md")

    def test_old_files_excluded(self):
        self._create_md("old.md", age_hours=48)  # 48 hours old
        result = scp._select_memory_files(self._tmp, last_n=10, window_hours=24)
        self.assertEqual(result, [])

    def test_last_n_limits_results(self):
        for i in range(5):
            self._create_md(f"file{i}.md", age_hours=0.1 * i)
        result = scp._select_memory_files(self._tmp, last_n=3, window_hours=24)
        self.assertEqual(len(result), 3)

    def test_sorted_newest_first(self):
        # Create files with different ages; result should be newest first
        old = self._create_md("old.md", age_hours=2)
        new = self._create_md("new.md", age_hours=0.1)
        result = scp._select_memory_files(self._tmp, last_n=10, window_hours=24)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].name, "new.md")
        self.assertEqual(result[1].name, "old.md")

    def test_non_md_files_ignored(self):
        (self._tmp / "notes.txt").write_text("not md", encoding="utf-8")
        (self._tmp / "data.json").write_text("{}", encoding="utf-8")
        self._create_md("valid.md", age_hours=0.5)
        result = scp._select_memory_files(self._tmp, last_n=10, window_hours=24)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "valid.md")

    def test_last_n_zero_returns_all(self):
        for i in range(3):
            self._create_md(f"file{i}.md", age_hours=0.1)
        result = scp._select_memory_files(self._tmp, last_n=0, window_hours=24)
        self.assertEqual(len(result), 3)


class TestWriteOutputs(unittest.TestCase):
    """Tests for write_outputs() — markdown report + JSON derived artifact."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_root = scp.REPO_ROOT
        scp.REPO_ROOT = self._tmp

    def tearDown(self):
        scp.REPO_ROOT = self._orig_root
        self._tmpdir.cleanup()

    def _make_report(self):
        return {
            "timestamp_utc": "2026-03-08T12:00:00Z",
            "seed": 23,
            "input_count": 2,
            "inputs": [
                {"path": "workspace/memory/foo.md", "chars_used": 100, "routing_confidence": 0.42},
            ],
            "derived": {"label": "test", "reservoir_state": {}},
        }

    def test_creates_report_md(self):
        report_md, _ = scp.write_outputs(self._make_report())
        self.assertTrue(report_md.exists())

    def test_creates_derived_json(self):
        _, derived_json = scp.write_outputs(self._make_report())
        self.assertTrue(derived_json.exists())

    def test_report_md_has_header(self):
        report_md, _ = scp.write_outputs(self._make_report())
        content = report_md.read_text(encoding="utf-8")
        self.assertIn("Sleep Consolidation Prototype Report", content)

    def test_derived_json_is_valid(self):
        _, derived_json = scp.write_outputs(self._make_report())
        loaded = json.loads(derived_json.read_text(encoding="utf-8"))
        self.assertEqual(loaded["seed"], 23)
        self.assertEqual(loaded["input_count"], 2)

    def test_derived_json_ends_with_newline(self):
        _, derived_json = scp.write_outputs(self._make_report())
        content = derived_json.read_text(encoding="utf-8")
        self.assertTrue(content.endswith("\n"))

    def test_report_includes_input_count(self):
        report_md, _ = scp.write_outputs(self._make_report())
        content = report_md.read_text(encoding="utf-8")
        self.assertIn("Input artifacts: 2", content)

    def test_report_includes_seed(self):
        report_md, _ = scp.write_outputs(self._make_report())
        content = report_md.read_text(encoding="utf-8")
        self.assertIn("Seed: 23", content)

    def test_output_filenames_contain_timestamp(self):
        report_md, derived_json = scp.write_outputs(self._make_report())
        # timestamp_utc = 2026-03-08T12:00:00Z → 20260308T120000Z
        self.assertIn("20260308", str(report_md.name))


if __name__ == "__main__":
    unittest.main()
