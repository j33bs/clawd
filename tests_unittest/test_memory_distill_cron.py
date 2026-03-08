import datetime as dt
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "workspace" / "scripts" / "memory_distill_cron.py"


class TestMemoryDistillCron(unittest.TestCase):
    def test_distills_distinct_events_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory_dir = root / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            (root / "workspace" / "state_runtime" / "memory").mkdir(parents=True, exist_ok=True)
            (root / "MEMORY.md").write_text("# MEMORY.md - Long-Term Context\n", encoding="utf-8")

            today = dt.date.today()
            yesterday = today - dt.timedelta(days=1)
            (memory_dir / f"{today.isoformat()}.md").write_text(
                "# Daily Memory\n\n## Actions\n- Fixed gateway crash loop\n- Fixed gateway crash loop\n- Rotated tokens\n",
                encoding="utf-8",
            )
            (memory_dir / f"{yesterday.isoformat()}.md").write_text(
                "# Daily Memory\n\n## Actions\n- Rotated tokens\n- Added watchdog timer\n",
                encoding="utf-8",
            )

            first = subprocess.run(
                ["python3", str(SCRIPT), "--repo-root", str(root), "--window-days", "2", "--max-items", "10"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            payload = json.loads(first.stdout.strip())
            self.assertTrue(payload["updated"])
            self.assertEqual(payload["added_events"], 3)

            memory_md = (root / "MEMORY.md").read_text(encoding="utf-8")
            self.assertIn("## Daily Distillations", memory_md)
            self.assertIn("- Fixed gateway crash loop", memory_md)
            self.assertIn("- Rotated tokens", memory_md)
            self.assertIn("- Added watchdog timer", memory_md)

            second = subprocess.run(
                ["python3", str(SCRIPT), "--repo-root", str(root), "--window-days", "2", "--max-items", "10"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            payload_2 = json.loads(second.stdout.strip())
            self.assertFalse(payload_2["updated"])
            self.assertEqual(payload_2["added_events"], 0)


class TestNormalizeKey(unittest.TestCase):
    """Unit tests for normalize_key() — pure function."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("memory_distill_cron", SCRIPT)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_lowercases(self):
        self.assertEqual(self.mod.normalize_key("HELLO"), "hello")

    def test_strips_whitespace(self):
        self.assertEqual(self.mod.normalize_key("  hello  "), "hello")

    def test_collapses_internal_spaces(self):
        self.assertEqual(self.mod.normalize_key("hello   world"), "hello world")

    def test_empty(self):
        self.assertEqual(self.mod.normalize_key(""), "")

    def test_tab_collapsed(self):
        self.assertEqual(self.mod.normalize_key("hello\tworld"), "hello world")


class TestParseDateFromName(unittest.TestCase):
    """Unit tests for parse_date_from_name()."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("memory_distill_cron", SCRIPT)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_valid_date(self):
        result = self.mod.parse_date_from_name(Path("/some/2026-03-08.md"))
        self.assertEqual(result, dt.date(2026, 3, 8))

    def test_non_date_stem_returns_none(self):
        result = self.mod.parse_date_from_name(Path("/some/MEMORY.md"))
        self.assertIsNone(result)

    def test_invalid_date_returns_none(self):
        result = self.mod.parse_date_from_name(Path("/some/2026-99-08.md"))
        self.assertIsNone(result)


class TestRecentDailyFiles(unittest.TestCase):
    """Unit tests for recent_daily_files()."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("memory_distill_cron", SCRIPT)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.memory_dir = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_empty_dir_returns_empty(self):
        result = self.mod.recent_daily_files(self.memory_dir, dt.date(2026, 3, 8), 3)
        self.assertEqual(result, [])

    def test_today_included(self):
        today = dt.date(2026, 3, 8)
        (self.memory_dir / "2026-03-08.md").touch()
        result = self.mod.recent_daily_files(self.memory_dir, today, 1)
        self.assertEqual(len(result), 1)

    def test_old_file_excluded(self):
        today = dt.date(2026, 3, 8)
        (self.memory_dir / "2026-01-01.md").touch()
        result = self.mod.recent_daily_files(self.memory_dir, today, 3)
        self.assertEqual(result, [])

    def test_non_date_files_excluded(self):
        today = dt.date(2026, 3, 8)
        (self.memory_dir / "MEMORY.md").touch()
        result = self.mod.recent_daily_files(self.memory_dir, today, 7)
        self.assertEqual(result, [])


class TestExtractBullets(unittest.TestCase):
    """Unit tests for extract_bullets()."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("memory_distill_cron", SCRIPT)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, content: str) -> Path:
        p = self.tmpdir / "f.md"
        p.write_text(content, encoding="utf-8")
        return p

    def test_empty_file_returns_empty(self):
        p = self._write("")
        self.assertEqual(self.mod.extract_bullets(p), [])

    def test_bullet_text_extracted(self):
        p = self._write("## Context\n- session focus: routing\n")
        result = self.mod.extract_bullets(p)
        self.assertEqual(result[0]["text"], "session focus: routing")

    def test_section_lowercased(self):
        p = self._write("## Actions\n- ran tests\n")
        result = self.mod.extract_bullets(p)
        self.assertEqual(result[0]["section"], "actions")

    def test_placeholder_excluded(self):
        p = self._write("## Section\n- \n- real bullet\n")
        result = self.mod.extract_bullets(p)
        self.assertEqual(len(result), 1)

    def test_key_field_present(self):
        p = self._write("## Section\n- Hello World\n")
        result = self.mod.extract_bullets(p)
        self.assertIn("key", result[0])
        self.assertEqual(result[0]["key"], "hello world")


if __name__ == "__main__":
    unittest.main()
