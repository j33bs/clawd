import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from memory_ext import ipnb_practices


class TestMemoryExtIPNB(unittest.TestCase):
    def test_off_by_default_does_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                result = ipnb_practices.somatic_checkin()
                self.assertFalse(result["enabled"])
                target = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "somatic_log.md"
                self.assertFalse(target.exists())

    def test_enabled_writes_and_recall(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                now = datetime(2026, 2, 25, 12, 0, tzinfo=timezone.utc)
                out = ipnb_practices.somatic_checkin(now=now)
                self.assertTrue(out["enabled"])
                recall = ipnb_practices.temporal_recall("all")
                self.assertGreaterEqual(len(recall["memory_entries"]), 1)
                self.assertIn("somatic_checkin", recall["themes"])
                rel = ipnb_practices.mwe_activator("we should co regulate together")
                self.assertEqual(rel["mode"], "co_regulated")
                vertical = ipnb_practices.vertical_integrate(4)
                self.assertTrue(vertical["integrated"])


# ---------------------------------------------------------------------------
# mwe_activator
# ---------------------------------------------------------------------------

class TestMweActivator(unittest.TestCase):
    """Tests for mwe_activator() — cue detection → co_regulated / individual."""

    def test_we_cue_gives_co_regulated(self):
        result = ipnb_practices.mwe_activator("we should work on this")
        self.assertEqual(result["mode"], "co_regulated")

    def test_together_cue(self):
        result = ipnb_practices.mwe_activator("let's do this together")
        self.assertEqual(result["mode"], "co_regulated")

    def test_us_cue(self):
        result = ipnb_practices.mwe_activator("between us")
        self.assertEqual(result["mode"], "co_regulated")

    def test_co_regulate_cue(self):
        result = ipnb_practices.mwe_activator("let's co-regulate")
        self.assertEqual(result["mode"], "co_regulated")

    def test_co_regulate_spaced_cue(self):
        result = ipnb_practices.mwe_activator("we co regulate here")
        self.assertEqual(result["mode"], "co_regulated")

    def test_with_you_cue(self):
        result = ipnb_practices.mwe_activator("I am with you")
        self.assertEqual(result["mode"], "co_regulated")

    def test_no_cue_gives_individual(self):
        result = ipnb_practices.mwe_activator("I think about this alone")
        self.assertEqual(result["mode"], "individual")

    def test_empty_string_gives_individual(self):
        result = ipnb_practices.mwe_activator("")
        self.assertEqual(result["mode"], "individual")

    def test_none_gives_individual(self):
        result = ipnb_practices.mwe_activator(None)
        self.assertEqual(result["mode"], "individual")

    def test_case_insensitive(self):
        result = ipnb_practices.mwe_activator("WE should work")
        self.assertEqual(result["mode"], "co_regulated")

    def test_returns_dict(self):
        result = ipnb_practices.mwe_activator("together")
        self.assertIsInstance(result, dict)

    def test_cue_field_populated(self):
        result = ipnb_practices.mwe_activator("we are here")
        self.assertIn("cue", result)
        self.assertEqual(result["cue"], "we")

    def test_cue_field_empty_when_individual(self):
        result = ipnb_practices.mwe_activator("I work alone")
        self.assertEqual(result["cue"], "")


# ---------------------------------------------------------------------------
# vertical_integrate
# ---------------------------------------------------------------------------

class TestVerticalIntegrate(unittest.TestCase):
    """Tests for vertical_integrate() — clamp [1,4], integrated=level>=2."""

    def test_level_2_integrated(self):
        result = ipnb_practices.vertical_integrate(2)
        self.assertTrue(result["integrated"])

    def test_level_4_integrated(self):
        result = ipnb_practices.vertical_integrate(4)
        self.assertTrue(result["integrated"])

    def test_level_1_not_integrated(self):
        result = ipnb_practices.vertical_integrate(1)
        self.assertFalse(result["integrated"])

    def test_below_1_clamped_to_1(self):
        result = ipnb_practices.vertical_integrate(-5)
        self.assertEqual(result["level_achieved"], 1)
        self.assertFalse(result["integrated"])

    def test_above_4_clamped_to_4(self):
        result = ipnb_practices.vertical_integrate(99)
        self.assertEqual(result["level_achieved"], 4)
        self.assertTrue(result["integrated"])

    def test_level_3_integrated(self):
        result = ipnb_practices.vertical_integrate(3)
        self.assertTrue(result["integrated"])

    def test_returns_dict(self):
        self.assertIsInstance(ipnb_practices.vertical_integrate(2), dict)

    def test_level_achieved_returned(self):
        result = ipnb_practices.vertical_integrate(3)
        self.assertEqual(result["level_achieved"], 3)


# ---------------------------------------------------------------------------
# _append_line
# ---------------------------------------------------------------------------

class TestAppendLine(unittest.TestCase):
    """Tests for _append_line() — creates parent dirs, appends with newline."""

    def test_creates_file_with_line(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nested" / "dir" / "log.md"
            ipnb_practices._append_line(path, "hello world")
            content = path.read_text(encoding="utf-8")
            self.assertIn("hello world", content)

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "a" / "b" / "c" / "file.txt"
            ipnb_practices._append_line(path, "test")
            self.assertTrue(path.exists())

    def test_appends_newline(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "log.md"
            ipnb_practices._append_line(path, "line1")
            content = path.read_text(encoding="utf-8")
            self.assertTrue(content.endswith("\n"))

    def test_multiple_appends(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "log.md"
            ipnb_practices._append_line(path, "line1")
            ipnb_practices._append_line(path, "line2")
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0], "line1")
            self.assertEqual(lines[1], "line2")

    def test_idempotent_parent(self):
        """Calling with existing parent dir should not raise."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "log.md"
            ipnb_practices._append_line(path, "first")
            ipnb_practices._append_line(path, "second")  # parent already exists
            self.assertTrue(path.exists())


# ---------------------------------------------------------------------------
# somatic_checkin (disabled / enabled)
# ---------------------------------------------------------------------------

class TestSomaticCheckin(unittest.TestCase):
    """Tests for somatic_checkin() — flag-guarded, writes log when enabled."""

    def test_disabled_returns_dict(self):
        with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
            result = ipnb_practices.somatic_checkin()
            self.assertIsInstance(result, dict)

    def test_disabled_enabled_false(self):
        with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
            result = ipnb_practices.somatic_checkin()
            self.assertFalse(result["enabled"])

    def test_disabled_ready_false(self):
        with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
            result = ipnb_practices.somatic_checkin()
            self.assertFalse(result["ready"])

    def test_disabled_no_file_written(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                ipnb_practices.somatic_checkin()
                target = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "somatic_log.md"
                self.assertFalse(target.exists())

    def test_enabled_returns_enabled_true(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                result = ipnb_practices.somatic_checkin()
                self.assertTrue(result["enabled"])

    def test_enabled_has_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                now = datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc)
                result = ipnb_practices.somatic_checkin(now=now)
                self.assertIn("timestamp_utc", result)
                self.assertIn("2026", result["timestamp_utc"])


# ---------------------------------------------------------------------------
# temporal_recall
# ---------------------------------------------------------------------------

class TestTemporalRecall(unittest.TestCase):
    """Tests for temporal_recall() — reads somatic log, filters by timeframe."""

    def test_no_log_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                result = ipnb_practices.temporal_recall("all")
                self.assertEqual(result["memory_entries"], [])
                self.assertEqual(result["themes"], [])

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                result = ipnb_practices.temporal_recall("all")
                self.assertIsInstance(result, dict)

    def test_with_entries_has_somatic_theme(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                ipnb_practices.somatic_checkin()
                result = ipnb_practices.temporal_recall("all")
                self.assertIn("somatic_checkin", result["themes"])

    def test_1_week_limits_to_7(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "somatic_log.md"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                "\n".join(f"- entry_{j}" for j in range(10)) + "\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                result = ipnb_practices.temporal_recall("1_week")
                self.assertLessEqual(len(result["memory_entries"]), 7)

    def test_1_month_limits_to_30(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "somatic_log.md"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                "\n".join(f"- entry_{j}" for j in range(50)) + "\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                result = ipnb_practices.temporal_recall("1_month")
                self.assertLessEqual(len(result["memory_entries"]), 30)

    def test_readiness_theme_when_ready_true(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "somatic_log.md"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("- 2026-03-08 felt_sense=clear ready=true\n", encoding="utf-8")
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                result = ipnb_practices.temporal_recall("all")
                self.assertIn("readiness", result["themes"])


if __name__ == "__main__":
    unittest.main()
