"""Tests for small pure helpers across misc script files.

Covers:
  audit_commit_hook.py: _flag_enabled, _repo_rel
  phi_session_runner.py: _utc_now, _detect_node
"""
import importlib.util as _ilu
import os
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"

# ---------------------------------------------------------------------------
# audit_commit_hook.py — stubs witness_ledger to allow clean module load
# ---------------------------------------------------------------------------

_wl_stub = types.ModuleType("witness_ledger")
_wl_stub.commit = None
sys.modules.setdefault("witness_ledger", _wl_stub)

_audit_spec = _ilu.spec_from_file_location(
    "audit_commit_hook_real",
    str(SCRIPTS_DIR / "audit_commit_hook.py"),
)
ach = _ilu.module_from_spec(_audit_spec)
sys.modules["audit_commit_hook_real"] = ach
_audit_spec.loader.exec_module(ach)


# ---------------------------------------------------------------------------
# phi_session_runner.py — stubs hivemind package to allow clean module load
# ---------------------------------------------------------------------------

_hivemind_stub = types.ModuleType("hivemind")
_hivemind_stub.__path__ = []
sys.modules.setdefault("hivemind", _hivemind_stub)
sys.modules.setdefault("hivemind.dynamics_pipeline", types.ModuleType("hivemind.dynamics_pipeline"))

_phi_spec = _ilu.spec_from_file_location(
    "phi_session_runner_real",
    str(SCRIPTS_DIR / "phi_session_runner.py"),
)
ps = _ilu.module_from_spec(_phi_spec)
sys.modules["phi_session_runner_real"] = ps
_phi_spec.loader.exec_module(ps)


# ---------------------------------------------------------------------------
# TestFlagEnabled (audit_commit_hook._flag_enabled)
# ---------------------------------------------------------------------------

class TestFlagEnabled(unittest.TestCase):
    """Tests for _flag_enabled() — reads env flag as bool."""

    def test_one_returns_true(self):
        with patch.dict(os.environ, {"MY_AUDIT_FLAG": "1"}):
            self.assertTrue(ach._flag_enabled("MY_AUDIT_FLAG"))

    def test_true_returns_true(self):
        with patch.dict(os.environ, {"MY_AUDIT_FLAG": "true"}):
            self.assertTrue(ach._flag_enabled("MY_AUDIT_FLAG"))

    def test_yes_returns_true(self):
        with patch.dict(os.environ, {"MY_AUDIT_FLAG": "yes"}):
            self.assertTrue(ach._flag_enabled("MY_AUDIT_FLAG"))

    def test_zero_returns_false(self):
        with patch.dict(os.environ, {"MY_AUDIT_FLAG": "0"}):
            self.assertFalse(ach._flag_enabled("MY_AUDIT_FLAG"))

    def test_missing_uses_default(self):
        env = {k: v for k, v in os.environ.items() if k != "MISSING_FLAG_XYZ"}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(ach._flag_enabled("MISSING_FLAG_XYZ"))

    def test_default_one_true(self):
        env = {k: v for k, v in os.environ.items() if k != "MISSING_FLAG_XYZ"}
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(ach._flag_enabled("MISSING_FLAG_XYZ", default="1"))

    def test_returns_bool(self):
        with patch.dict(os.environ, {"MY_FLAG": "1"}):
            result = ach._flag_enabled("MY_FLAG")
            self.assertIsInstance(result, bool)


# ---------------------------------------------------------------------------
# TestRepoRel (audit_commit_hook._repo_rel)
# ---------------------------------------------------------------------------

class TestRepoRel(unittest.TestCase):
    """Tests for _repo_rel() — returns path relative to WORKSPACE_ROOT."""

    def test_child_path_relative(self):
        # ach.WORKSPACE_ROOT is workspace/scripts/../ = workspace of the repo
        workspace_root = ach.WORKSPACE_ROOT
        child = workspace_root / "somefile.txt"
        result = ach._repo_rel(child)
        self.assertEqual(result, "somefile.txt")

    def test_nested_path_uses_posix(self):
        workspace_root = ach.WORKSPACE_ROOT
        child = workspace_root / "subdir" / "file.json"
        result = ach._repo_rel(child)
        self.assertEqual(result, "subdir/file.json")

    def test_non_relative_path_returns_str(self):
        # A path that can't be made relative returns str(path) not raising
        result = ach._repo_rel(Path("/totally/different/path.txt"))
        self.assertIsInstance(result, str)

    def test_returns_string(self):
        result = ach._repo_rel(ach.WORKSPACE_ROOT)
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# TestPhiUtcNow (phi_session_runner._utc_now)
# ---------------------------------------------------------------------------

class TestPhiUtcNow(unittest.TestCase):
    """Tests for phi_session_runner._utc_now() — UTC ISO string."""

    def test_returns_string(self):
        result = ps._utc_now()
        self.assertIsInstance(result, str)

    def test_ends_with_z(self):
        result = ps._utc_now()
        self.assertTrue(result.endswith("Z"))

    def test_no_microseconds(self):
        # replace(microsecond=0) ensures no fractional seconds
        result = ps._utc_now()
        self.assertNotIn(".", result)

    def test_parseable(self):
        result = ps._utc_now()
        # convert Z to +00:00 for fromisoformat
        datetime.fromisoformat(result.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# TestDetectNode (phi_session_runner._detect_node)
# ---------------------------------------------------------------------------

class TestDetectNode(unittest.TestCase):
    """Tests for phi_session_runner._detect_node() — node ID from env."""

    def test_env_override_used(self):
        with patch.dict(os.environ, {"OPENCLAW_NODE_ID": "MyNode"}):
            result = ps._detect_node()
            self.assertEqual(result, "MyNode")

    def test_default_value(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_NODE_ID"}
        with patch.dict(os.environ, env, clear=True):
            result = ps._detect_node()
            self.assertEqual(result, "Dali/C_Lawd")

    def test_returns_string(self):
        result = ps._detect_node()
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
