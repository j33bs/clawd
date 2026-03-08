"""Tests for sync_dreams.py — dream consolidation → MEMORY.md pipeline."""
import json
import tempfile
import unittest
from pathlib import Path

import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import sync_dreams as sd


class TestFormatDreamBlock(unittest.TestCase):
    def test_basic_block_format(self):
        dream = {
            "total_events": 10,
            "successes": 8,
            "failures": 2,
            "event_types": {"tacti_cr.prefetch": 5, "test.event": 3, "other": 2},
        }
        block = sd._format_dream_block("2026-03-07", dream)
        self.assertIn("2026-03-07 (dream-summary)", block)
        self.assertIn("Total events: 10", block)
        self.assertIn("successes: 8", block)
        self.assertIn("failures: 2", block)
        self.assertIn("tacti_cr.prefetch×5", block)

    def test_high_success_flag(self):
        dream = {"total_events": 10, "successes": 9, "failures": 1, "event_types": {}}
        block = sd._format_dream_block("2026-03-07", dream)
        self.assertIn("✅ High-success session", block)

    def test_failure_dominant_flag(self):
        dream = {"total_events": 10, "successes": 2, "failures": 8, "event_types": {}}
        block = sd._format_dream_block("2026-03-07", dream)
        self.assertIn("⚠️ Failure-dominant session", block)

    def test_zero_events_no_flag(self):
        dream = {"total_events": 0, "successes": 0, "failures": 0, "event_types": {}}
        block = sd._format_dream_block("2026-03-07", dream)
        self.assertNotIn("✅", block)
        self.assertNotIn("⚠️", block)

    def test_top_event_types_capped_at_three(self):
        dream = {
            "total_events": 100,
            "successes": 0,
            "failures": 0,
            "event_types": {f"type_{i}": 10 - i for i in range(5)},
        }
        block = sd._format_dream_block("2026-03-07", dream)
        # Should have at most 3 types in top_str
        self.assertIn("type_0×10", block)
        self.assertIn("type_1×9", block)
        self.assertIn("type_2×8", block)
        self.assertNotIn("type_3×7", block)


class TestEnsureHeader(unittest.TestCase):
    def test_adds_header_if_missing(self):
        content = "# MEMORY\n\n## Some section\nsome content\n"
        result = sd._ensure_header(content)
        self.assertIn(sd.DAILY_HEADER, result)

    def test_does_not_duplicate_header(self):
        content = f"# MEMORY\n\n{sd.DAILY_HEADER}\n"
        result = sd._ensure_header(content)
        self.assertEqual(result.count(sd.DAILY_HEADER), 1)

    def test_appends_newline_if_needed(self):
        content = "no trailing newline"
        result = sd._ensure_header(content)
        self.assertIn(sd.DAILY_HEADER, result)


class TestLoadDream(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_valid_json_returned(self):
        p = self._tmp / "2026-03-07.json"
        data = {"total_events": 5, "successes": 3, "failures": 1, "event_types": {}}
        p.write_text(json.dumps(data), encoding="utf-8")
        result = sd._load_dream(p)
        self.assertEqual(result["total_events"], 5)

    def test_invalid_json_returns_none(self):
        p = self._tmp / "bad.json"
        p.write_text("not json", encoding="utf-8")
        result = sd._load_dream(p)
        self.assertIsNone(result)

    def test_missing_file_returns_none(self):
        p = self._tmp / "missing.json"
        result = sd._load_dream(p)
        self.assertIsNone(result)


class TestSync(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig = {
            "DREAMS_DIR": sd.DREAMS_DIR,
            "MEMORY_MD": sd.MEMORY_MD,
            "SYNC_STATE": sd.SYNC_STATE,
        }
        sd.DREAMS_DIR = self._tmp / "dreams"
        sd.MEMORY_MD = self._tmp / "MEMORY.md"
        sd.SYNC_STATE = self._tmp / ".dreams_synced.json"

    def tearDown(self):
        for attr, val in self._orig.items():
            setattr(sd, attr, val)
        self._tmpdir.cleanup()

    def _write_dream(self, date_str: str, data: dict) -> None:
        sd.DREAMS_DIR.mkdir(parents=True, exist_ok=True)
        (sd.DREAMS_DIR / f"{date_str}.json").write_text(json.dumps(data), encoding="utf-8")

    def test_no_dreams_dir_returns_status(self):
        result = sd.sync()
        self.assertEqual(result["status"], "no_dreams_dir")

    def test_no_dream_files_returns_status(self):
        sd.DREAMS_DIR.mkdir(parents=True, exist_ok=True)
        result = sd.sync()
        self.assertEqual(result["status"], "no_dreams")

    def test_syncs_dream_to_memory_md(self):
        dream = {"total_events": 10, "successes": 8, "failures": 2, "event_types": {}}
        self._write_dream("2026-03-07", dream)
        result = sd.sync()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["synced"], 1)
        # MEMORY.md should now contain the dream summary
        content = sd.MEMORY_MD.read_text(encoding="utf-8")
        self.assertIn("2026-03-07 (dream-summary)", content)

    def test_idempotent_on_second_run(self):
        dream = {"total_events": 10, "successes": 8, "failures": 2, "event_types": {}}
        self._write_dream("2026-03-07", dream)
        sd.sync()
        result = sd.sync()
        self.assertEqual(result["status"], "up_to_date")
        self.assertEqual(result["synced"], 0)

    def test_dry_run_does_not_write(self):
        dream = {"total_events": 10, "successes": 8, "failures": 2, "event_types": {}}
        self._write_dream("2026-03-07", dream)
        result = sd.sync(dry_run=True)
        self.assertEqual(result["status"], "dry_run")
        self.assertFalse(sd.MEMORY_MD.exists())

    def test_error_dream_skipped(self):
        sd.DREAMS_DIR.mkdir(parents=True, exist_ok=True)
        # Dream with error field is skipped
        (sd.DREAMS_DIR / "2026-03-07.json").write_text(
            json.dumps({"error": "No events file"}), encoding="utf-8"
        )
        result = sd.sync()
        self.assertIn(result["status"], ("no_dreams", "up_to_date"))

    def test_daily_header_added_to_empty_memory_md(self):
        sd.MEMORY_MD.write_text("", encoding="utf-8")
        dream = {"total_events": 5, "successes": 5, "failures": 0, "event_types": {}}
        self._write_dream("2026-03-08", dream)
        sd.sync()
        content = sd.MEMORY_MD.read_text(encoding="utf-8")
        self.assertIn(sd.DAILY_HEADER, content)


if __name__ == "__main__":
    unittest.main()
