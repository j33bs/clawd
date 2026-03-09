"""Tests for reject_disallowed_tool_calls() in workspace/local_exec/model_client.py.

reject_disallowed_tool_calls() is a pure side-effect function that raises
ModelClientError when a disallowed tool name is encountered.

Covers:
- Empty list → no error
- Allowed tool → no error
- Disallowed tool → raises ModelClientError with tool name
- Edge cases: None call, missing function key, missing name key
"""
import unittest

from workspace.local_exec.model_client import ModelClientError, reject_disallowed_tool_calls


class TestRejectDisallowedToolCalls(unittest.TestCase):
    """Tests for reject_disallowed_tool_calls(tool_calls, allowed_tools)."""

    def test_empty_list_no_error(self):
        reject_disallowed_tool_calls([], set())

    def test_empty_allowed_set_empty_list_no_error(self):
        reject_disallowed_tool_calls([], set())

    def test_allowed_tool_no_error(self):
        calls = [{"function": {"name": "read_file"}}]
        reject_disallowed_tool_calls(calls, {"read_file"})

    def test_multiple_allowed_tools_no_error(self):
        calls = [
            {"function": {"name": "read_file"}},
            {"function": {"name": "write_file"}},
        ]
        reject_disallowed_tool_calls(calls, {"read_file", "write_file"})

    def test_disallowed_tool_raises_model_client_error(self):
        calls = [{"function": {"name": "bash"}}]
        with self.assertRaises(ModelClientError):
            reject_disallowed_tool_calls(calls, {"read_file"})

    def test_disallowed_tool_error_message_contains_tool_name(self):
        calls = [{"function": {"name": "delete_all"}}]
        try:
            reject_disallowed_tool_calls(calls, set())
            self.fail("Expected ModelClientError")
        except ModelClientError as e:
            self.assertIn("delete_all", str(e))

    def test_disallowed_tool_error_prefix(self):
        calls = [{"function": {"name": "network_call"}}]
        try:
            reject_disallowed_tool_calls(calls, set())
        except ModelClientError as e:
            self.assertIn("disallowed_tool_call", str(e))

    def test_empty_allowed_set_with_tool_raises(self):
        calls = [{"function": {"name": "anything"}}]
        with self.assertRaises(ModelClientError):
            reject_disallowed_tool_calls(calls, set())

    def test_none_call_in_list_skipped(self):
        # call=None → fn_name = None → no raise
        reject_disallowed_tool_calls([None], set())

    def test_call_without_function_key_skipped(self):
        calls = [{"type": "tool_call"}]
        reject_disallowed_tool_calls(calls, set())

    def test_call_without_name_key_skipped(self):
        calls = [{"function": {}}]
        reject_disallowed_tool_calls(calls, set())

    def test_function_name_none_skipped(self):
        calls = [{"function": {"name": None}}]
        reject_disallowed_tool_calls(calls, set())

    def test_first_disallowed_raises_immediately(self):
        # Should raise on the disallowed call, not process the rest
        calls = [
            {"function": {"name": "allowed"}},
            {"function": {"name": "bad"}},
            {"function": {"name": "also_allowed"}},
        ]
        with self.assertRaises(ModelClientError) as ctx:
            reject_disallowed_tool_calls(calls, {"allowed", "also_allowed"})
        self.assertIn("bad", str(ctx.exception))

    def test_model_client_error_is_exception(self):
        self.assertTrue(issubclass(ModelClientError, Exception))


if __name__ == "__main__":
    unittest.main()
