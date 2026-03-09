"""Tests for pure helpers in workspace/router/validate_control_plane.py.

Covers:
- _scenario_prompts() — returns list of test scenario dicts
- _count_log_lines(path) — counts lines in a JSONL file
- _find_latest_log_by_reason(path, reason_tag) — finds last matching row
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "router" / "validate_control_plane.py"

_spec = _ilu.spec_from_file_location("validate_control_plane_real", str(MODULE_PATH))
vcp = _ilu.module_from_spec(_spec)
sys.modules["validate_control_plane_real"] = vcp
_spec.loader.exec_module(vcp)

_scenario_prompts = vcp._scenario_prompts
_count_log_lines = vcp._count_log_lines
_find_latest_log_by_reason = vcp._find_latest_log_by_reason


# ---------------------------------------------------------------------------
# _scenario_prompts
# ---------------------------------------------------------------------------


class TestScenarioPrompts(unittest.TestCase):
    """Tests for _scenario_prompts() — returns validation scenario list."""

    def test_returns_list(self):
        self.assertIsInstance(_scenario_prompts(), list)

    def test_returns_five_scenarios(self):
        self.assertEqual(len(_scenario_prompts()), 5)

    def test_all_have_name(self):
        for s in _scenario_prompts():
            self.assertIn("name", s)

    def test_all_have_prompt(self):
        for s in _scenario_prompts():
            self.assertIn("prompt", s)

    def test_all_prompts_are_non_empty(self):
        for s in _scenario_prompts():
            self.assertTrue(s["prompt"].strip())

    def test_scenario_names_are_unique(self):
        names = [s["name"] for s in _scenario_prompts()]
        self.assertEqual(len(names), len(set(names)))

    def test_knowledge_mlx_forced_has_expected_backend(self):
        scenarios = {s["name"]: s for s in _scenario_prompts()}
        self.assertIn("knowledge_mlx_forced", scenarios)
        self.assertEqual(scenarios["knowledge_mlx_forced"]["expected_backend"], "mlx")

    def test_knowledge_mlx_forced_has_force_intent(self):
        scenarios = {s["name"]: s for s in _scenario_prompts()}
        self.assertEqual(scenarios["knowledge_mlx_forced"]["force_intent"], "research")

    def test_returns_new_list_each_call(self):
        a = _scenario_prompts()
        b = _scenario_prompts()
        self.assertIsNot(a, b)

    def test_conversation_scenario_present(self):
        names = [s["name"] for s in _scenario_prompts()]
        self.assertIn("conversation", names)


# ---------------------------------------------------------------------------
# _count_log_lines
# ---------------------------------------------------------------------------


class TestCountLogLines(unittest.TestCase):
    """Tests for _count_log_lines(path) — counts non-empty file lines."""

    def test_nonexistent_path_returns_zero(self):
        p = Path("/tmp/does_not_exist_ever_12345.jsonl")
        self.assertEqual(_count_log_lines(p), 0)

    def test_empty_file_returns_zero(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            p = Path(f.name)
        try:
            p.write_text("", encoding="utf-8")
            self.assertEqual(_count_log_lines(p), 0)
        finally:
            p.unlink(missing_ok=True)

    def test_one_line_returns_one(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"event": "test"}\n')
            p = Path(f.name)
        try:
            self.assertEqual(_count_log_lines(p), 1)
        finally:
            p.unlink(missing_ok=True)

    def test_three_lines_returns_three(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"a": 1}\n{"b": 2}\n{"c": 3}\n')
            p = Path(f.name)
        try:
            self.assertEqual(_count_log_lines(p), 3)
        finally:
            p.unlink(missing_ok=True)

    def test_no_trailing_newline_still_counts(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"x": 1}\n{"y": 2}')
            p = Path(f.name)
        try:
            self.assertEqual(_count_log_lines(p), 2)
        finally:
            p.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# _find_latest_log_by_reason
# ---------------------------------------------------------------------------


class TestFindLatestLogByReason(unittest.TestCase):
    """Tests for _find_latest_log_by_reason() — scans JSONL for last match."""

    def _write_jsonl(self, rows):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        for row in rows:
            f.write(json.dumps(row) + "\n")
        f.close()
        return Path(f.name)

    def test_nonexistent_path_returns_none(self):
        p = Path("/tmp/does_not_exist_12345.jsonl")
        self.assertIsNone(_find_latest_log_by_reason(p, "tag:x"))

    def test_no_matching_row_returns_none(self):
        p = self._write_jsonl([{"reason_tag": "other", "val": 1}])
        try:
            self.assertIsNone(_find_latest_log_by_reason(p, "tag:x"))
        finally:
            p.unlink(missing_ok=True)

    def test_returns_matching_row(self):
        rows = [{"reason_tag": "tag:x", "val": 42}]
        p = self._write_jsonl(rows)
        try:
            result = _find_latest_log_by_reason(p, "tag:x")
            self.assertIsNotNone(result)
            self.assertEqual(result["val"], 42)
        finally:
            p.unlink(missing_ok=True)

    def test_returns_last_matching_row(self):
        rows = [
            {"reason_tag": "tag:x", "val": 1},
            {"reason_tag": "tag:other", "val": 99},
            {"reason_tag": "tag:x", "val": 2},
        ]
        p = self._write_jsonl(rows)
        try:
            result = _find_latest_log_by_reason(p, "tag:x")
            self.assertEqual(result["val"], 2)
        finally:
            p.unlink(missing_ok=True)

    def test_skips_corrupt_lines(self):
        p = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        p.write("not json\n")
        p.write(json.dumps({"reason_tag": "tag:x", "val": 5}) + "\n")
        p.close()
        path = Path(p.name)
        try:
            result = _find_latest_log_by_reason(path, "tag:x")
            self.assertEqual(result["val"], 5)
        finally:
            path.unlink(missing_ok=True)

    def test_skips_blank_lines(self):
        p = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        p.write("\n\n")
        p.write(json.dumps({"reason_tag": "tag:y", "v": 7}) + "\n")
        p.close()
        path = Path(p.name)
        try:
            result = _find_latest_log_by_reason(path, "tag:y")
            self.assertEqual(result["v"], 7)
        finally:
            path.unlink(missing_ok=True)

    def test_returns_dict(self):
        rows = [{"reason_tag": "mytag", "x": 1}]
        p = self._write_jsonl(rows)
        try:
            result = _find_latest_log_by_reason(p, "mytag")
            self.assertIsInstance(result, dict)
        finally:
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
