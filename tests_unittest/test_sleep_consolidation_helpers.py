"""Tests for pure helpers in workspace/scripts/sleep_consolidation_prototype.py.

Covers:
- _utc_now() — ISO UTC timestamp ending in 'Z'
- _select_memory_files(memory_dir, last_n, window_hours) — recent .md file filter
"""
import importlib.util as _ilu
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "sleep_consolidation_prototype.py"

# hivemind.reservoir needed at module load
_hivemind_dir = str(REPO_ROOT / "workspace" / "hivemind")
if _hivemind_dir not in sys.path:
    sys.path.insert(0, _hivemind_dir)

_spec = _ilu.spec_from_file_location("sleep_consolidation_real", str(SCRIPT_PATH))
sc = _ilu.module_from_spec(_spec)
sys.modules["sleep_consolidation_real"] = sc
_spec.loader.exec_module(sc)

_utc_now = sc._utc_now
_select_memory_files = sc._select_memory_files


# ---------------------------------------------------------------------------
# _utc_now
# ---------------------------------------------------------------------------


class TestUtcNow(unittest.TestCase):
    """Tests for _utc_now() — returns ISO UTC timestamp."""

    def test_returns_string(self):
        self.assertIsInstance(_utc_now(), str)

    def test_ends_with_z(self):
        self.assertTrue(_utc_now().endswith("Z"))

    def test_contains_t_separator(self):
        self.assertIn("T", _utc_now())

    def test_no_offset_string(self):
        self.assertNotIn("+00:00", _utc_now())

    def test_no_microseconds(self):
        # Format should be HH:MM:SS not HH:MM:SS.ffffff
        ts = _utc_now()
        time_part = ts.split("T")[1].rstrip("Z")
        self.assertNotIn(".", time_part)


# ---------------------------------------------------------------------------
# _select_memory_files
# ---------------------------------------------------------------------------


class TestSelectMemoryFiles(unittest.TestCase):
    """Tests for _select_memory_files() — filters recent .md files."""

    def _write_file(self, directory, name, age_seconds=0):
        """Create a file with a controlled mtime."""
        path = directory / name
        path.write_text("content", encoding="utf-8")
        mtime = time.time() - age_seconds
        os.utime(path, (mtime, mtime))
        return path

    def test_empty_dir_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _select_memory_files(Path(tmp), last_n=10, window_hours=1)
            self.assertEqual(result, [])

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _select_memory_files(Path(tmp), last_n=10, window_hours=24)
            self.assertIsInstance(result, list)

    def test_recent_md_file_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            f = self._write_file(d, "recent.md", age_seconds=60)
            result = _select_memory_files(d, last_n=10, window_hours=1)
            self.assertIn(f, result)

    def test_non_md_file_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self._write_file(d, "file.txt", age_seconds=0)
            self._write_file(d, "file.json", age_seconds=0)
            result = _select_memory_files(d, last_n=10, window_hours=1)
            self.assertEqual(result, [])

    def test_old_md_file_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            # 25 hours ago — outside 24-hour window
            self._write_file(d, "old.md", age_seconds=25 * 3600)
            result = _select_memory_files(d, last_n=10, window_hours=24)
            self.assertEqual(result, [])

    def test_last_n_limits_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for i in range(5):
                self._write_file(d, f"file{i}.md", age_seconds=i * 10)
            result = _select_memory_files(d, last_n=2, window_hours=1)
            self.assertEqual(len(result), 2)

    def test_last_n_zero_returns_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for i in range(4):
                self._write_file(d, f"file{i}.md", age_seconds=i * 10)
            result = _select_memory_files(d, last_n=0, window_hours=1)
            self.assertEqual(len(result), 4)

    def test_result_sorted_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            old = self._write_file(d, "old.md", age_seconds=200)
            new = self._write_file(d, "new.md", age_seconds=10)
            result = _select_memory_files(d, last_n=10, window_hours=1)
            self.assertEqual(result[0], new)
            self.assertEqual(result[1], old)

    def test_all_returned_are_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self._write_file(d, "test.md", age_seconds=0)
            result = _select_memory_files(d, last_n=10, window_hours=1)
            for item in result:
                self.assertIsInstance(item, Path)


if __name__ == "__main__":
    unittest.main()
