"""Tests for team_chat_adapters — _contains_shell_metacharacters, _is_allowed_command,
_extract_json_object, _coerce_work_orders, _detect_pause_stuck."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import team_chat_adapters as tca


class TestContainsShellMetacharacters(unittest.TestCase):
    """Tests for _contains_shell_metacharacters() — shell injection detection."""

    def test_pipe_detected(self):
        self.assertTrue(tca._contains_shell_metacharacters("ls | grep foo"))

    def test_semicolon_detected(self):
        self.assertTrue(tca._contains_shell_metacharacters("cmd; rm -rf"))

    def test_ampersand_detected(self):
        self.assertTrue(tca._contains_shell_metacharacters("cmd && evil"))

    def test_backtick_detected(self):
        self.assertTrue(tca._contains_shell_metacharacters("`whoami`"))

    def test_redirect_in_detected(self):
        self.assertTrue(tca._contains_shell_metacharacters("cmd < /etc/passwd"))

    def test_redirect_out_detected(self):
        self.assertTrue(tca._contains_shell_metacharacters("cmd > output.txt"))

    def test_safe_command_no_detection(self):
        self.assertFalse(tca._contains_shell_metacharacters("git status"))

    def test_safe_with_spaces_no_detection(self):
        self.assertFalse(tca._contains_shell_metacharacters("python3 -m pytest tests/"))

    def test_empty_string_safe(self):
        self.assertFalse(tca._contains_shell_metacharacters(""))

    def test_hyphen_safe(self):
        # Hyphens are not shell metacharacters
        self.assertFalse(tca._contains_shell_metacharacters("npm test --watch"))


class TestIsAllowedCommand(unittest.TestCase):
    """Tests for _is_allowed_command() — security allowlist gate."""

    def test_empty_command_disallowed(self):
        self.assertFalse(tca._is_allowed_command(""))

    def test_pipe_injection_disallowed(self):
        self.assertFalse(tca._is_allowed_command("git status | rm -rf /"))

    def test_git_status_allowed(self):
        self.assertTrue(tca._is_allowed_command("git status"))

    def test_git_diff_allowed(self):
        self.assertTrue(tca._is_allowed_command("git diff"))

    def test_git_log_allowed(self):
        self.assertTrue(tca._is_allowed_command("git log"))

    def test_git_clone_disallowed(self):
        # git clone is not in the allowed list
        self.assertFalse(tca._is_allowed_command("git clone https://evil.com"))

    def test_python3_py_compile_allowed(self):
        self.assertTrue(tca._is_allowed_command("python3 -m py_compile"))

    def test_npm_test_allowed(self):
        self.assertTrue(tca._is_allowed_command("npm test"))

    def test_rm_rf_disallowed(self):
        self.assertFalse(tca._is_allowed_command("rm -rf /"))

    def test_semicolon_injection_disallowed(self):
        self.assertFalse(tca._is_allowed_command("git status; rm -rf"))

    def test_extra_patterns_extend_allowlist(self):
        # A custom pattern should allow a command not otherwise in the list
        self.assertTrue(
            tca._is_allowed_command(
                "echo hello",
                extra_patterns=[r"^echo\s+"],
            )
        )

    def test_whitespace_stripped(self):
        self.assertTrue(tca._is_allowed_command("  git status  "))


class TestExtractJsonObject(unittest.TestCase):
    """Tests for _extract_json_object() — JSON dict extraction from arbitrary text."""

    def test_plain_json_dict_parsed(self):
        result = tca._extract_json_object('{"key": "value"}')
        self.assertEqual(result, {"key": "value"})

    def test_json_with_surrounding_text(self):
        result = tca._extract_json_object('Here is the result: {"x": 1} done')
        self.assertEqual(result, {"x": 1})

    def test_nested_json(self):
        result = tca._extract_json_object('{"a": {"b": 2}}')
        self.assertIsNotNone(result)
        self.assertEqual(result["a"]["b"], 2)

    def test_empty_string_returns_none(self):
        result = tca._extract_json_object("")
        self.assertIsNone(result)

    def test_none_input_returns_none(self):
        result = tca._extract_json_object(None)  # type: ignore
        self.assertIsNone(result)

    def test_plain_text_returns_none(self):
        result = tca._extract_json_object("no json here at all")
        self.assertIsNone(result)

    def test_json_list_returns_none(self):
        # List is not a dict → returns None
        result = tca._extract_json_object("[1, 2, 3]")
        self.assertIsNone(result)

    def test_empty_dict(self):
        result = tca._extract_json_object("{}")
        self.assertEqual(result, {})

    def test_json_with_prefix_prose(self):
        text = "I suggest the following work order:\n\n```json\n{\"title\": \"test\"}\n```"
        result = tca._extract_json_object(text)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("title"), "test")

    def test_invalid_json_returns_none(self):
        result = tca._extract_json_object("{bad json}")
        self.assertIsNone(result)


class TestCoerceWorkOrders(unittest.TestCase):
    """Tests for _coerce_work_orders() — work order normalization and validation."""

    def _make_order(self, **kwargs):
        base = {
            "title": "Test Task",
            "goal": "Do something",
            "commands": ["python3 -m pytest"],
            "tests": ["python3 -m pytest tests/"],
            "notes": "Notes here",
        }
        base.update(kwargs)
        return base

    def test_non_list_returns_empty(self):
        self.assertEqual(tca._coerce_work_orders("string"), [])
        self.assertEqual(tca._coerce_work_orders(None), [])
        self.assertEqual(tca._coerce_work_orders({}), [])

    def test_empty_list_returns_empty(self):
        self.assertEqual(tca._coerce_work_orders([]), [])

    def test_valid_order_included(self):
        result = tca._coerce_work_orders([self._make_order()])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Test Task")

    def test_missing_title_skipped(self):
        no_title = {"goal": "no title here", "commands": []}
        result = tca._coerce_work_orders([no_title])
        self.assertEqual(result, [])

    def test_non_dict_items_skipped(self):
        result = tca._coerce_work_orders(["string", 42, None, self._make_order()])
        self.assertEqual(len(result), 1)

    def test_id_auto_assigned_when_missing(self):
        order = self._make_order()
        order.pop("id", None)
        result = tca._coerce_work_orders([order])
        self.assertEqual(result[0]["id"], "wo-1")

    def test_id_preserved_when_present(self):
        order = self._make_order(id="custom-id-123")
        result = tca._coerce_work_orders([order])
        self.assertEqual(result[0]["id"], "custom-id-123")

    def test_commands_coerced_to_strings(self):
        order = self._make_order(commands=["cmd1", "cmd2"])
        result = tca._coerce_work_orders([order])
        self.assertEqual(result[0]["commands"], ["cmd1", "cmd2"])

    def test_non_string_commands_filtered(self):
        order = self._make_order(commands=["valid", 42, None, "also_valid"])
        result = tca._coerce_work_orders([order])
        # Only string items survive
        self.assertEqual(result[0]["commands"], ["valid", "also_valid"])

    def test_empty_goal_becomes_empty_string(self):
        order = self._make_order(goal=None)
        result = tca._coerce_work_orders([order])
        self.assertEqual(result[0]["goal"], "")

    def test_multiple_orders_all_included(self):
        orders = [self._make_order(title=f"Task {i}") for i in range(3)]
        result = tca._coerce_work_orders(orders)
        self.assertEqual(len(result), 3)
        titles = [r["title"] for r in result]
        self.assertIn("Task 0", titles)
        self.assertIn("Task 2", titles)


class TestDetectPauseStuck(unittest.TestCase):
    """Tests for _detect_pause_stuck() — stuck classifier detection."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_log(self, entries: list[dict]) -> Path:
        path = self._tmp / "pause_log.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return path

    def _make_entry(self, decision="PAUSE", fills_space=0.85, value_add=0.0, silence_ok=True):
        return {
            "decision": decision,
            "signals": {"fills_space": fills_space, "value_add": value_add, "silence_ok": silence_ok},
        }

    def test_missing_file_returns_false(self):
        result = tca._detect_pause_stuck(self._tmp / "nonexistent.jsonl")
        self.assertFalse(result)

    def test_too_few_entries_returns_false(self):
        entries = [self._make_entry()] * 3  # threshold=5 by default
        path = self._write_log(entries)
        result = tca._detect_pause_stuck(path, threshold=5)
        self.assertFalse(result)

    def test_identical_entries_at_threshold_returns_true(self):
        threshold = 5
        entries = [self._make_entry()] * threshold
        path = self._write_log(entries)
        result = tca._detect_pause_stuck(path, threshold=threshold)
        self.assertTrue(result)

    def test_varied_entries_returns_false(self):
        entries = [
            self._make_entry(decision="PAUSE", fills_space=0.85),
            self._make_entry(decision="PROCEED", fills_space=0.2),
            self._make_entry(decision="PAUSE", fills_space=0.9),
            self._make_entry(decision="PAUSE", fills_space=0.1),
            self._make_entry(decision="PAUSE", fills_space=0.85),
        ]
        path = self._write_log(entries)
        result = tca._detect_pause_stuck(path, threshold=5)
        self.assertFalse(result)

    def test_only_last_n_entries_checked(self):
        # First 3 are varied, last 5 are identical → should be stuck
        threshold = 5
        varied = [
            self._make_entry(decision="A"),
            self._make_entry(decision="B"),
            self._make_entry(decision="C"),
        ]
        identical = [self._make_entry()] * threshold
        path = self._write_log(varied + identical)
        result = tca._detect_pause_stuck(path, threshold=threshold)
        self.assertTrue(result)

    def test_invalid_json_line_returns_false(self):
        path = self._tmp / "bad_log.jsonl"
        path.write_text("not json\n" * 5, encoding="utf-8")
        result = tca._detect_pause_stuck(path, threshold=5)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
