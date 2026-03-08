"""Tests for workspace/memory_ext/ipnb_practices.py pure helpers.

Stubs _common module for the `from _common import` fallback.
Directly testable: mwe_activator, vertical_integrate, _append_line,
temporal_recall.

Covers:
- mwe_activator
- vertical_integrate
- _append_line
- temporal_recall
"""
import importlib.util as _ilu
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
MEM_EXT_DIR = REPO_ROOT / "workspace" / "memory_ext"

# Add memory_ext dir to sys.path so the real `_common` is importable.
# Do NOT stub it in sys.modules — that would break test_memory_ext_common.py
# which also needs the real _common module.
if str(MEM_EXT_DIR) not in sys.path:
    sys.path.insert(0, str(MEM_EXT_DIR))

_spec = _ilu.spec_from_file_location(
    "ipnb_practices_real",
    str(MEM_EXT_DIR / "ipnb_practices.py"),
)
ip = _ilu.module_from_spec(_spec)
sys.modules["ipnb_practices_real"] = ip
_spec.loader.exec_module(ip)


# ---------------------------------------------------------------------------
# mwe_activator
# ---------------------------------------------------------------------------

class TestMweActivator(unittest.TestCase):
    """Tests for mwe_activator() — detects co-regulation cues in text."""

    def test_no_cue_returns_individual(self):
        result = ip.mwe_activator("I need help")
        self.assertEqual(result["mode"], "individual")
        self.assertEqual(result["cue"], "")

    def test_we_cue_detected(self):
        result = ip.mwe_activator("can we work on this together?")
        self.assertEqual(result["mode"], "co_regulated")
        self.assertIn(result["cue"], {"we", "together"})

    def test_together_cue(self):
        result = ip.mwe_activator("let's do this together")
        self.assertEqual(result["mode"], "co_regulated")

    def test_case_insensitive(self):
        result = ip.mwe_activator("WE can solve this")
        self.assertEqual(result["mode"], "co_regulated")

    def test_empty_string_individual(self):
        result = ip.mwe_activator("")
        self.assertEqual(result["mode"], "individual")

    def test_returns_dict_with_mode_and_cue(self):
        result = ip.mwe_activator("hello")
        self.assertIn("mode", result)
        self.assertIn("cue", result)


# ---------------------------------------------------------------------------
# vertical_integrate
# ---------------------------------------------------------------------------

class TestVerticalIntegrate(unittest.TestCase):
    """Tests for vertical_integrate() — checks integration level threshold."""

    def test_level_1_not_integrated(self):
        result = ip.vertical_integrate(1)
        self.assertFalse(result["integrated"])

    def test_level_2_integrated(self):
        result = ip.vertical_integrate(2)
        self.assertTrue(result["integrated"])

    def test_level_4_integrated(self):
        result = ip.vertical_integrate(4)
        self.assertTrue(result["integrated"])

    def test_level_below_1_clamped_to_1(self):
        result = ip.vertical_integrate(-5)
        self.assertEqual(result["level_achieved"], 1)

    def test_level_above_4_clamped_to_4(self):
        result = ip.vertical_integrate(99)
        self.assertEqual(result["level_achieved"], 4)

    def test_returns_dict(self):
        result = ip.vertical_integrate(2)
        self.assertIsInstance(result, dict)
        self.assertIn("integrated", result)
        self.assertIn("level_achieved", result)


# ---------------------------------------------------------------------------
# _append_line
# ---------------------------------------------------------------------------

class TestAppendLine(unittest.TestCase):
    """Tests for _append_line() — appends a text line to a file."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "log.md"
            ip._append_line(p, "hello")
            self.assertTrue(p.exists())

    def test_content_written(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.md"
            ip._append_line(p, "entry one")
            self.assertIn("entry one", p.read_text(encoding="utf-8"))

    def test_multiple_appends(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.md"
            ip._append_line(p, "line 1")
            ip._append_line(p, "line 2")
            lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l]
            self.assertEqual(len(lines), 2)

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a" / "b" / "log.md"
            ip._append_line(p, "x")
            self.assertTrue(p.parent.is_dir())


# ---------------------------------------------------------------------------
# temporal_recall
# ---------------------------------------------------------------------------

class TestTemporalRecall(unittest.TestCase):
    """Tests for temporal_recall() — reads somatic log entries."""

    def test_missing_log_returns_empty(self):
        # Patch _somatic_log_path to point to nonexistent file
        with patch.object(ip, "_somatic_log_path", return_value=Path("/no/log.md")):
            result = ip.temporal_recall("all")
        self.assertEqual(result["memory_entries"], [])
        self.assertEqual(result["themes"], [])

    def test_entries_returned(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.md"
            p.write_text("- entry one\n- entry two\n", encoding="utf-8")
            with patch.object(ip, "_somatic_log_path", return_value=p):
                result = ip.temporal_recall("all")
        self.assertEqual(len(result["memory_entries"]), 2)

    def test_1_week_limits_to_7(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.md"
            p.write_text("\n".join(f"- entry{i}" for i in range(15)) + "\n", encoding="utf-8")
            with patch.object(ip, "_somatic_log_path", return_value=p):
                result = ip.temporal_recall("1_week")
        self.assertLessEqual(len(result["memory_entries"]), 7)

    def test_readiness_theme_added_when_ready(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.md"
            p.write_text("- ts felt_sense=clear ready=true\n", encoding="utf-8")
            with patch.object(ip, "_somatic_log_path", return_value=p):
                result = ip.temporal_recall("all")
        self.assertIn("readiness", result["themes"])

    def test_somatic_checkin_theme_always_added_when_entries(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.md"
            p.write_text("- some entry\n", encoding="utf-8")
            with patch.object(ip, "_somatic_log_path", return_value=p):
                result = ip.temporal_recall("all")
        self.assertIn("somatic_checkin", result["themes"])

    def test_returns_dict(self):
        with patch.object(ip, "_somatic_log_path", return_value=Path("/no/log.md")):
            result = ip.temporal_recall("all")
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
