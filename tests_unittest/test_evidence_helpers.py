"""Tests for workspace/local_exec/evidence.py pure helper functions.

Covers (tempfile-backed I/O):
- evidence_dir
- append_event
- append_worker_event
- write_summary
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_EXEC_DIR = REPO_ROOT / "workspace" / "local_exec"
if str(LOCAL_EXEC_DIR) not in sys.path:
    sys.path.insert(0, str(LOCAL_EXEC_DIR))

from evidence import (  # noqa: E402
    append_event,
    append_worker_event,
    evidence_dir,
    write_summary,
)


# ---------------------------------------------------------------------------
# evidence_dir
# ---------------------------------------------------------------------------

class TestEvidenceDir(unittest.TestCase):
    """Tests for evidence_dir() — creates and returns evidence directory path."""

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as td:
            result = evidence_dir(Path(td))
            self.assertIsInstance(result, Path)

    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as td:
            result = evidence_dir(Path(td))
            self.assertTrue(result.exists())
            self.assertTrue(result.is_dir())

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d1 = evidence_dir(root)
            d2 = evidence_dir(root)
            self.assertEqual(d1, d2)

    def test_under_repo_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = evidence_dir(root)
            self.assertTrue(str(result).startswith(td))


# ---------------------------------------------------------------------------
# append_event
# ---------------------------------------------------------------------------

class TestAppendEvent(unittest.TestCase):
    """Tests for append_event() — JSONL event writer."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = append_event(Path(td), "job1", "start", {"x": 1})
            self.assertTrue(path.exists())

    def test_file_has_valid_json_line(self):
        with tempfile.TemporaryDirectory() as td:
            path = append_event(Path(td), "job2", "done", {"status": "ok"})
            line = path.read_text(encoding="utf-8").strip()
            row = json.loads(line)
            self.assertEqual(row["job_id"], "job2")
            self.assertEqual(row["kind"], "done")
            self.assertEqual(row["payload"]["status"], "ok")

    def test_appends_multiple_events(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            append_event(root, "job3", "start", {})
            path = append_event(root, "job3", "end", {})
            lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(len(lines), 2)

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as td:
            result = append_event(Path(td), "job4", "check", {})
            self.assertIsInstance(result, Path)

    def test_ts_utc_field_present(self):
        with tempfile.TemporaryDirectory() as td:
            path = append_event(Path(td), "job5", "ping", {})
            row = json.loads(path.read_text().strip())
            self.assertIn("ts_utc", row)


# ---------------------------------------------------------------------------
# append_worker_event
# ---------------------------------------------------------------------------

class TestAppendWorkerEvent(unittest.TestCase):
    """Tests for append_worker_event() — per-worker JSONL writer."""

    def test_creates_worker_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = append_worker_event(Path(td), "worker1", "start", {"n": 0})
            self.assertTrue(path.exists())

    def test_sanitizes_slash_in_worker_id(self):
        with tempfile.TemporaryDirectory() as td:
            path = append_worker_event(Path(td), "pool/worker2", "start", {})
            self.assertNotIn("/", path.name.replace("worker_", ""))

    def test_worker_id_in_row(self):
        with tempfile.TemporaryDirectory() as td:
            path = append_worker_event(Path(td), "wk1", "done", {})
            row = json.loads(path.read_text().strip())
            self.assertEqual(row["worker_id"], "wk1")

    def test_kind_in_row(self):
        with tempfile.TemporaryDirectory() as td:
            path = append_worker_event(Path(td), "wk2", "heartbeat", {"beat": 1})
            row = json.loads(path.read_text().strip())
            self.assertEqual(row["kind"], "heartbeat")

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as td:
            result = append_worker_event(Path(td), "wk3", "x", {})
            self.assertIsInstance(result, Path)


# ---------------------------------------------------------------------------
# write_summary
# ---------------------------------------------------------------------------

class TestWriteSummary(unittest.TestCase):
    """Tests for write_summary() — writes markdown summary file."""

    def test_creates_md_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_summary(Path(td), "job-md1", "# Summary\nDone.")
            self.assertTrue(path.exists())

    def test_content_correct(self):
        with tempfile.TemporaryDirectory() as td:
            content = "## Result\nAll good."
            path = write_summary(Path(td), "job-md2", content)
            self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as td:
            result = write_summary(Path(td), "job-md3", "text")
            self.assertIsInstance(result, Path)

    def test_file_ends_with_job_id_md(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_summary(Path(td), "myjob", "content")
            self.assertTrue(path.name.endswith(".md"))
            self.assertIn("myjob", path.name)


if __name__ == "__main__":
    unittest.main()
