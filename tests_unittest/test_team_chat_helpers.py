"""Tests for pure helpers in workspace/scripts/team_chat.py.

Stubs team_chat_adapters to allow clean module load.
Covers (no network, no subprocess calls, minimal file I/O):
- _truthy
- _parse_bool
- _guard_controls
- utc_now
- append_jsonl
- load_state
- save_state
- check_resumable
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"

# Stub team_chat_adapters so the top-level import doesn't fail
if "team_chat_adapters" not in sys.modules:
    _tca_stub = types.ModuleType("team_chat_adapters")
    _tca_stub.build_adapters = lambda *a, **kw: {}
    sys.modules["team_chat_adapters"] = _tca_stub

_spec = _ilu.spec_from_file_location(
    "team_chat_real",
    str(SCRIPTS_DIR / "team_chat.py"),
)
tc = _ilu.module_from_spec(_spec)
sys.modules["team_chat_real"] = tc
_spec.loader.exec_module(tc)

_truthy = tc._truthy
_parse_bool = tc._parse_bool
_guard_controls = tc._guard_controls
utc_now = tc.utc_now
append_jsonl = tc.append_jsonl
load_state = tc.load_state
save_state = tc.save_state
check_resumable = tc.check_resumable


# ---------------------------------------------------------------------------
# _truthy
# ---------------------------------------------------------------------------

class TestTruthy(unittest.TestCase):
    """Tests for _truthy() — coerce value to bool from common truthy strings."""

    def test_one_is_true(self):
        self.assertTrue(_truthy("1"))

    def test_true_is_true(self):
        self.assertTrue(_truthy("true"))

    def test_yes_is_true(self):
        self.assertTrue(_truthy("yes"))

    def test_on_is_true(self):
        self.assertTrue(_truthy("on"))

    def test_zero_is_false(self):
        self.assertFalse(_truthy("0"))

    def test_empty_is_false(self):
        self.assertFalse(_truthy(""))

    def test_none_is_false(self):
        self.assertFalse(_truthy(None))

    def test_arbitrary_string_false(self):
        self.assertFalse(_truthy("maybe"))

    def test_case_insensitive(self):
        self.assertTrue(_truthy("TRUE"))
        self.assertTrue(_truthy("Yes"))

    def test_returns_bool(self):
        self.assertIsInstance(_truthy("1"), bool)


# ---------------------------------------------------------------------------
# _parse_bool
# ---------------------------------------------------------------------------

class TestParseBool(unittest.TestCase):
    """Tests for _parse_bool() — parse bool from bool/str/None with default."""

    def test_true_bool_passthrough(self):
        self.assertTrue(_parse_bool(True))

    def test_false_bool_passthrough(self):
        self.assertFalse(_parse_bool(False))

    def test_none_uses_default_false(self):
        self.assertFalse(_parse_bool(None))

    def test_none_uses_default_true(self):
        self.assertTrue(_parse_bool(None, default=True))

    def test_string_true(self):
        self.assertTrue(_parse_bool("1"))
        self.assertTrue(_parse_bool("true"))
        self.assertTrue(_parse_bool("yes"))
        self.assertTrue(_parse_bool("on"))

    def test_string_false(self):
        self.assertFalse(_parse_bool("0"))
        self.assertFalse(_parse_bool("false"))
        self.assertFalse(_parse_bool("no"))
        self.assertFalse(_parse_bool("off"))

    def test_unknown_string_uses_default(self):
        self.assertFalse(_parse_bool("maybe", default=False))
        self.assertTrue(_parse_bool("maybe", default=True))

    def test_returns_bool(self):
        self.assertIsInstance(_parse_bool("1"), bool)


# ---------------------------------------------------------------------------
# _guard_controls
# ---------------------------------------------------------------------------

class TestGuardControls(unittest.TestCase):
    """Tests for _guard_controls() — autocommit/patch safety gating logic."""

    def _call(self, branch="dev", auto=False, accept=False, arm="", dirty=False, allow_dirty=False):
        return _guard_controls(
            branch=branch,
            requested_auto_commit=auto,
            requested_accept_patches=accept,
            requested_commit_arm=arm,
            allow_dirty=allow_dirty,
            repo_dirty=dirty,
        )

    def test_protected_branch_blocks_auto(self):
        result = self._call(branch="main", auto=True, accept=True, arm="I_UNDERSTAND")
        self.assertFalse(result["final_auto_commit"])
        self.assertTrue(result["protected_branch"])

    def test_master_is_protected(self):
        result = self._call(branch="master", auto=True, accept=True, arm="I_UNDERSTAND")
        self.assertFalse(result["final_auto_commit"])

    def test_armed_dev_branch_enabled(self):
        result = self._call(branch="dev", auto=True, accept=True, arm="I_UNDERSTAND")
        self.assertTrue(result["final_auto_commit"])
        self.assertTrue(result["final_accept_patches"])

    def test_missing_arm_blocked(self):
        result = self._call(branch="dev", auto=True, accept=True, arm="")
        self.assertFalse(result["final_auto_commit"])
        self.assertTrue(result["commit_not_armed"])

    def test_dirty_tree_blocks_auto(self):
        result = self._call(branch="dev", auto=True, accept=True, arm="I_UNDERSTAND", dirty=True, allow_dirty=False)
        self.assertFalse(result["final_auto_commit"])
        self.assertTrue(result["dirty_tree_blocked"])

    def test_allow_dirty_passes_dirty_tree(self):
        result = self._call(branch="dev", auto=True, accept=True, arm="I_UNDERSTAND", dirty=True, allow_dirty=True)
        self.assertTrue(result["final_auto_commit"])
        self.assertFalse(result["dirty_tree_blocked"])

    def test_no_auto_commit_not_armed_unset(self):
        result = self._call(branch="dev", auto=False)
        self.assertFalse(result["commit_not_armed"])

    def test_returns_dict(self):
        result = self._call()
        self.assertIsInstance(result, dict)
        self.assertIn("final_auto_commit", result)
        self.assertIn("final_accept_patches", result)


# ---------------------------------------------------------------------------
# utc_now
# ---------------------------------------------------------------------------

class TestUtcNow(unittest.TestCase):
    """Tests for utc_now() — UTC ISO timestamp string."""

    def test_returns_string(self):
        self.assertIsInstance(utc_now(), str)

    def test_ends_with_z(self):
        self.assertTrue(utc_now().endswith("Z"))

    def test_parseable(self):
        datetime.strptime(utc_now(), "%Y-%m-%dT%H:%M:%SZ")

    def test_no_microseconds(self):
        self.assertNotIn(".", utc_now())


# ---------------------------------------------------------------------------
# append_jsonl
# ---------------------------------------------------------------------------

class TestAppendJsonl(unittest.TestCase):
    """Tests for append_jsonl() — append a JSON object as a line to a file."""

    def test_creates_file_and_parent(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "subdir" / "log.jsonl"
            append_jsonl(p, {"key": "value"})
            self.assertTrue(p.exists())

    def test_appended_content_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            append_jsonl(p, {"x": 42})
            line = p.read_text(encoding="utf-8").strip()
            data = json.loads(line)
            self.assertEqual(data["x"], 42)

    def test_multiple_appends(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            append_jsonl(p, {"n": 1})
            append_jsonl(p, {"n": 2})
            lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(len(lines), 2)


# ---------------------------------------------------------------------------
# load_state
# ---------------------------------------------------------------------------

class TestLoadState(unittest.TestCase):
    """Tests for load_state() — JSON state loader with dict merge."""

    def test_missing_file_returns_default(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            result = load_state(p, {"foo": "bar"})
            self.assertEqual(result["foo"], "bar")

    def test_existing_file_merged(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            p.write_text(json.dumps({"foo": "overridden", "extra": 99}), encoding="utf-8")
            result = load_state(p, {"foo": "default", "missing": "X"})
            self.assertEqual(result["foo"], "overridden")
            self.assertEqual(result["extra"], 99)
            self.assertEqual(result["missing"], "X")

    def test_invalid_json_returns_default(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            p.write_text("NOT JSON", encoding="utf-8")
            result = load_state(p, {"fallback": True})
            self.assertTrue(result["fallback"])

    def test_non_dict_json_returns_default(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            result = load_state(p, {"fallback": True})
            self.assertTrue(result["fallback"])

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            result = load_state(Path(td) / "missing.json", {})
            self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# save_state
# ---------------------------------------------------------------------------

class TestSaveState(unittest.TestCase):
    """Tests for save_state() — write state dict to JSON with updated_at."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "state.json"
            save_state(p, {"value": 42})
            self.assertTrue(p.exists())

    def test_content_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            save_state(p, {"cycle": 3})
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(data["cycle"], 3)

    def test_updated_at_added(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            save_state(p, {"x": 1})
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertIn("updated_at", data)

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a" / "b" / "state.json"
            save_state(p, {})
            self.assertTrue(p.parent.is_dir())


# ---------------------------------------------------------------------------
# check_resumable
# ---------------------------------------------------------------------------

class TestCheckResumable(unittest.TestCase):
    """Tests for check_resumable() — session resume eligibility check."""

    def test_stopped_not_resumable(self):
        self.assertFalse(check_resumable({"status": "stopped:user_request"}))

    def test_accepted_not_resumable(self):
        self.assertFalse(check_resumable({"status": "accepted"}))

    def test_request_input_not_resumable(self):
        self.assertFalse(check_resumable({"status": "request_input"}))

    def test_running_is_resumable(self):
        self.assertTrue(check_resumable({"status": "running"}))

    def test_empty_status_is_resumable(self):
        self.assertTrue(check_resumable({"status": ""}))

    def test_missing_status_is_resumable(self):
        self.assertTrue(check_resumable({}))

    def test_returns_bool(self):
        self.assertIsInstance(check_resumable({}), bool)


if __name__ == "__main__":
    unittest.main()
