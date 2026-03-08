"""Tests for pure helpers in workspace/local_exec/worker.py.

Stubs all local_exec sub-package dependencies so only stdlib logic runs.

Covers:
- _stable_hash
- _model_runtime
- _match_any
- _ensure_policy
- _bounded_argv
"""
import importlib.util as _ilu
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_EXEC_DIR = REPO_ROOT / "workspace" / "local_exec"


def _ensure_local_exec_pkg():
    """Install local_exec package + all sub-module stubs."""
    if "local_exec" not in sys.modules:
        pkg = types.ModuleType("local_exec")
        pkg.__path__ = [str(LOCAL_EXEC_DIR)]
        pkg.__package__ = "local_exec"
        sys.modules["local_exec"] = pkg

    # budgets
    if "local_exec.budgets" not in sys.modules:
        bud = types.ModuleType("local_exec.budgets")
        bud.BudgetExceeded = RuntimeError
        bud.BudgetLimits = None
        bud.BudgetTracker = None
        bud.kill_switch_enabled = lambda *a, **kw: False
        sys.modules["local_exec.budgets"] = bud
        setattr(sys.modules["local_exec"], "budgets", bud)
    else:
        bud = sys.modules["local_exec.budgets"]
        if not hasattr(bud, "BudgetExceeded"):
            bud.BudgetExceeded = RuntimeError
        if not hasattr(bud, "kill_switch_enabled"):
            bud.kill_switch_enabled = lambda *a, **kw: False

    # evidence
    if "local_exec.evidence" not in sys.modules:
        ev = types.ModuleType("local_exec.evidence")
        ev.append_event = lambda *a, **kw: None
        ev.append_worker_event = lambda *a, **kw: None
        ev.write_summary = lambda *a, **kw: None
        sys.modules["local_exec.evidence"] = ev
        setattr(sys.modules["local_exec"], "evidence", ev)
    else:
        ev = sys.modules["local_exec.evidence"]
        if not hasattr(ev, "append_event"):
            ev.append_event = lambda *a, **kw: None
        if not hasattr(ev, "write_summary"):
            ev.write_summary = lambda *a, **kw: None

    # queue
    if "local_exec.queue" not in sys.modules:
        q = types.ModuleType("local_exec.queue")
        q.claim_next_job = lambda *a, **kw: None
        q.complete_job = lambda *a, **kw: None
        q.fail_job = lambda *a, **kw: None
        q.heartbeat = lambda *a, **kw: None
        sys.modules["local_exec.queue"] = q
        setattr(sys.modules["local_exec"], "queue", q)
    else:
        q = sys.modules["local_exec.queue"]
        for attr in ("claim_next_job", "complete_job", "fail_job", "heartbeat"):
            if not hasattr(q, attr):
                setattr(q, attr, lambda *a, **kw: None)

    # subprocess_harness
    if "local_exec.subprocess_harness" not in sys.modules:
        sh = types.ModuleType("local_exec.subprocess_harness")
        sh.SubprocessPolicyError = RuntimeError
        sh.resolve_repo_path = lambda *a, **kw: Path("/tmp")
        sh.run_argv = lambda *a, **kw: {"returncode": 0, "stdout": "", "stderr": ""}
        sys.modules["local_exec.subprocess_harness"] = sh
        setattr(sys.modules["local_exec"], "subprocess_harness", sh)
    else:
        sh = sys.modules["local_exec.subprocess_harness"]
        if not hasattr(sh, "SubprocessPolicyError"):
            sh.SubprocessPolicyError = RuntimeError

    # validation
    if "local_exec.validation" not in sys.modules:
        val = types.ModuleType("local_exec.validation")
        val.validator_mode = lambda: "lite"
        sys.modules["local_exec.validation"] = val
        setattr(sys.modules["local_exec"], "validation", val)
    else:
        val = sys.modules["local_exec.validation"]
        if not hasattr(val, "validator_mode"):
            val.validator_mode = lambda: "lite"


_ensure_local_exec_pkg()

_spec = _ilu.spec_from_file_location(
    "local_exec_worker_real",
    str(LOCAL_EXEC_DIR / "worker.py"),
)
wk = _ilu.module_from_spec(_spec)
wk.__package__ = "local_exec"
sys.modules["local_exec_worker_real"] = wk
_spec.loader.exec_module(wk)


# ---------------------------------------------------------------------------
# _stable_hash
# ---------------------------------------------------------------------------

class TestStableHash(unittest.TestCase):
    """Tests for _stable_hash() — sorted JSON + sha256[:16]."""

    def test_returns_string(self):
        result = wk._stable_hash({"a": 1})
        self.assertIsInstance(result, str)

    def test_returns_16_chars(self):
        result = wk._stable_hash({"key": "value"})
        self.assertEqual(len(result), 16)

    def test_deterministic(self):
        a = wk._stable_hash({"x": 1, "y": 2})
        b = wk._stable_hash({"x": 1, "y": 2})
        self.assertEqual(a, b)

    def test_key_order_independent(self):
        # sort_keys=True means {"a":1,"b":2} == {"b":2,"a":1}
        a = wk._stable_hash({"a": 1, "b": 2})
        b = wk._stable_hash({"b": 2, "a": 1})
        self.assertEqual(a, b)

    def test_different_payloads_differ(self):
        a = wk._stable_hash({"x": 1})
        b = wk._stable_hash({"x": 2})
        self.assertNotEqual(a, b)

    def test_empty_dict(self):
        result = wk._stable_hash({})
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 16)


# ---------------------------------------------------------------------------
# _model_runtime
# ---------------------------------------------------------------------------

class TestModelRuntime(unittest.TestCase):
    """Tests for _model_runtime() — reads env vars for model config."""

    def test_returns_dict(self):
        result = wk._model_runtime()
        self.assertIsInstance(result, dict)

    def test_has_model_mode(self):
        result = wk._model_runtime()
        self.assertIn("model_mode", result)

    def test_has_api_base(self):
        result = wk._model_runtime()
        self.assertIn("api_base", result)

    def test_has_model_name(self):
        result = wk._model_runtime()
        self.assertIn("model_name", result)

    def test_default_model_mode_stub(self):
        # Default: OPENCLAW_LOCAL_EXEC_MODEL_STUB not set or == "1" → "stub"
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_LOCAL_EXEC_MODEL_STUB"}
        with patch.dict(os.environ, env, clear=True):
            result = wk._model_runtime()
        self.assertEqual(result["model_mode"], "stub")

    def test_model_mode_live_when_zero(self):
        with patch.dict(os.environ, {"OPENCLAW_LOCAL_EXEC_MODEL_STUB": "0"}):
            result = wk._model_runtime()
        self.assertEqual(result["model_mode"], "live")

    def test_model_name_env_override(self):
        with patch.dict(os.environ, {"OPENCLAW_LOCAL_EXEC_MODEL": "gpt-4"}):
            result = wk._model_runtime()
        self.assertEqual(result["model_name"], "gpt-4")


# ---------------------------------------------------------------------------
# _match_any
# ---------------------------------------------------------------------------

class TestMatchAny(unittest.TestCase):
    """Tests for _match_any() — fnmatch against list of patterns."""

    def test_matches_star_py(self):
        self.assertTrue(wk._match_any("foo/bar.py", ["*.py"]))

    def test_no_match(self):
        self.assertFalse(wk._match_any("foo/bar.txt", ["*.py"]))

    def test_empty_globs_returns_false(self):
        self.assertFalse(wk._match_any("anything.py", []))

    def test_star_matches_all(self):
        self.assertTrue(wk._match_any("some/path/file.rs", ["*"]))

    def test_multiple_patterns_one_matches(self):
        self.assertTrue(wk._match_any("file.ts", ["*.py", "*.ts", "*.js"]))

    def test_multiple_patterns_none_match(self):
        self.assertFalse(wk._match_any("file.go", ["*.py", "*.ts"]))


# ---------------------------------------------------------------------------
# _ensure_policy
# ---------------------------------------------------------------------------

class TestEnsurePolicy(unittest.TestCase):
    """Tests for _ensure_policy() — raises RuntimeError on policy violations."""

    def _job(self, allow_subprocess=False, allow_network=False):
        return {
            "tool_policy": {
                "allow_subprocess": allow_subprocess,
                "allow_network": allow_network,
                "allowed_tools": [],
            }
        }

    def test_no_requirements_no_raise(self):
        wk._ensure_policy(self._job())  # should not raise

    def test_subprocess_allowed_when_permitted(self):
        wk._ensure_policy(self._job(allow_subprocess=True), requires_subprocess=True)

    def test_subprocess_raises_when_not_allowed(self):
        with self.assertRaises(RuntimeError):
            wk._ensure_policy(self._job(allow_subprocess=False), requires_subprocess=True)

    def test_network_raises_when_not_allowed(self):
        with self.assertRaises(RuntimeError):
            wk._ensure_policy(self._job(allow_network=False), requires_network=True)

    def test_network_allowed_when_permitted(self):
        wk._ensure_policy(self._job(allow_network=True), requires_network=True)

    def test_invalid_tool_policy_raises(self):
        job = {"tool_policy": "not-a-dict"}
        with self.assertRaises(RuntimeError):
            wk._ensure_policy(job)


# ---------------------------------------------------------------------------
# _bounded_argv
# ---------------------------------------------------------------------------

class TestBoundedArgv(unittest.TestCase):
    """Tests for _bounded_argv() — truncates argv list and parts."""

    def test_short_unchanged(self):
        argv = ["python", "-m", "pytest"]
        result = wk._bounded_argv(argv)
        self.assertEqual(result, argv)

    def test_long_part_truncated_to_256(self):
        long_arg = "x" * 300
        result = wk._bounded_argv([long_arg])
        self.assertEqual(len(result[0]), 256)

    def test_long_list_truncated_to_64(self):
        argv = [f"arg{i}" for i in range(100)]
        result = wk._bounded_argv(argv)
        self.assertEqual(len(result), 64)

    def test_empty_argv(self):
        result = wk._bounded_argv([])
        self.assertEqual(result, [])

    def test_returns_list(self):
        result = wk._bounded_argv(["a", "b"])
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
