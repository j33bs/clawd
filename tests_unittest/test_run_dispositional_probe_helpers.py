"""Tests for pure helpers in workspace/scripts/run_dispositional_probe.py.

Covers:
- _utc_now() — ISO UTC timestamp ending in 'Z'
- _load_questions(path) — numbered line parser from probe .md file
"""
import importlib.util as _ilu
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "run_dispositional_probe.py"

_spec = _ilu.spec_from_file_location("run_dispositional_probe_real", str(SCRIPT_PATH))
_mod = _ilu.module_from_spec(_spec)
sys.modules["run_dispositional_probe_real"] = _mod
_spec.loader.exec_module(_mod)

_utc_now = _mod._utc_now
_load_questions = _mod._load_questions


# ---------------------------------------------------------------------------
# _utc_now
# ---------------------------------------------------------------------------


class TestUtcNow(unittest.TestCase):
    """Tests for _utc_now() — ISO UTC timestamp string."""

    def test_returns_string(self):
        self.assertIsInstance(_utc_now(), str)

    def test_ends_with_z(self):
        self.assertTrue(_utc_now().endswith("Z"))

    def test_no_offset_string(self):
        self.assertNotIn("+00:00", _utc_now())

    def test_contains_t_separator(self):
        self.assertIn("T", _utc_now())

    def test_no_microseconds(self):
        ts = _utc_now()
        time_part = ts.split("T")[1].rstrip("Z")
        self.assertNotIn(".", time_part)


# ---------------------------------------------------------------------------
# _load_questions
# ---------------------------------------------------------------------------


class TestLoadQuestions(unittest.TestCase):
    """Tests for _load_questions(path) — numbered line parser."""

    def _write(self, content):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        return Path(f.name)

    def test_empty_file_returns_empty_list(self):
        p = self._write("")
        try:
            self.assertEqual(_load_questions(p), [])
        finally:
            p.unlink(missing_ok=True)

    def test_returns_list(self):
        p = self._write("1. Hello?\n")
        try:
            self.assertIsInstance(_load_questions(p), list)
        finally:
            p.unlink(missing_ok=True)

    def test_single_numbered_question(self):
        p = self._write("1. What is your goal?\n")
        try:
            result = _load_questions(p)
            self.assertEqual(result, ["What is your goal?"])
        finally:
            p.unlink(missing_ok=True)

    def test_strips_number_prefix(self):
        p = self._write("2. Second question\n")
        try:
            result = _load_questions(p)
            self.assertEqual(result[0], "Second question")
        finally:
            p.unlink(missing_ok=True)

    def test_skips_blank_lines(self):
        p = self._write("\n\n1. Only this\n\n")
        try:
            result = _load_questions(p)
            self.assertEqual(result, ["Only this"])
        finally:
            p.unlink(missing_ok=True)

    def test_skips_non_numbered_lines(self):
        p = self._write("# Header\nSome prose\n1. Real question\n")
        try:
            result = _load_questions(p)
            self.assertEqual(result, ["Real question"])
        finally:
            p.unlink(missing_ok=True)

    def test_multiple_questions_in_order(self):
        content = "1. First\n2. Second\n3. Third\n"
        p = self._write(content)
        try:
            result = _load_questions(p)
            self.assertEqual(result, ["First", "Second", "Third"])
        finally:
            p.unlink(missing_ok=True)

    def test_two_digit_number_included(self):
        p = self._write("10. Tenth question\n")
        try:
            result = _load_questions(p)
            self.assertEqual(result, ["Tenth question"])
        finally:
            p.unlink(missing_ok=True)

    def test_no_space_after_dot_excluded(self):
        # "1.NoSpace" does not contain ". " so it is excluded
        p = self._write("1.NoSpace\n")
        try:
            result = _load_questions(p)
            self.assertEqual(result, [])
        finally:
            p.unlink(missing_ok=True)

    def test_line_starting_with_letter_excluded(self):
        p = self._write("A. Not numbered\n")
        try:
            result = _load_questions(p)
            self.assertEqual(result, [])
        finally:
            p.unlink(missing_ok=True)

    def test_question_text_split_at_first_dot_space(self):
        # "1. a. b" should extract "a. b" (split on first ". " only)
        p = self._write("1. a. b\n")
        try:
            result = _load_questions(p)
            self.assertEqual(result, ["a. b"])
        finally:
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
