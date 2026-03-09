"""Tests for pure helpers in scripts/local_exec_enqueue.py.

Stubs workspace.local_exec.queue before module load.

Covers:
- utc_now()
- default_budgets()
- default_tool_policy()
- build_demo_job()
"""
import importlib.util as _ilu
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = REPO_ROOT / "workspace"
SCRIPT_PATH = REPO_ROOT / "scripts" / "local_exec_enqueue.py"


def _ensure_stubs():
    """Try real import first; only stub workspace.local_exec.queue if unavailable."""
    try:
        import importlib
        importlib.import_module("workspace.local_exec.queue")
        # Real module loaded — no stub needed
        return
    except Exception:
        pass

    # Real module unavailable — register minimal stub
    if "workspace" not in sys.modules:
        wp = types.ModuleType("workspace")
        wp.__path__ = [str(WORKSPACE_DIR)]
        wp.__package__ = "workspace"
        sys.modules["workspace"] = wp

    if "workspace.local_exec" not in sys.modules:
        le = types.ModuleType("workspace.local_exec")
        le.__path__ = [str(WORKSPACE_DIR / "local_exec")]
        le.__package__ = "workspace.local_exec"
        sys.modules["workspace.local_exec"] = le

    if "workspace.local_exec.queue" not in sys.modules:
        q = types.ModuleType("workspace.local_exec.queue")
        q.enqueue_job = lambda repo_root, job: {"ts_utc": "2024-01-01T00:00:00Z"}
        sys.modules["workspace.local_exec.queue"] = q
        setattr(sys.modules["workspace.local_exec"], "queue", q)


_ensure_stubs()

_spec = _ilu.spec_from_file_location("local_exec_enqueue_real", str(SCRIPT_PATH))
le_enqueue = _ilu.module_from_spec(_spec)
sys.modules["local_exec_enqueue_real"] = le_enqueue
_spec.loader.exec_module(le_enqueue)

utc_now = le_enqueue.utc_now
default_budgets = le_enqueue.default_budgets
default_tool_policy = le_enqueue.default_tool_policy
build_demo_job = le_enqueue.build_demo_job


# ---------------------------------------------------------------------------
# utc_now
# ---------------------------------------------------------------------------


class TestUtcNow(unittest.TestCase):
    """Tests for utc_now() — returns ISO UTC string ending in 'Z'."""

    def test_returns_string(self):
        result = utc_now()
        self.assertIsInstance(result, str)

    def test_ends_with_z(self):
        result = utc_now()
        self.assertTrue(result.endswith("Z"))

    def test_contains_t_separator(self):
        result = utc_now()
        self.assertIn("T", result)

    def test_no_offset_string(self):
        result = utc_now()
        self.assertNotIn("+00:00", result)

    def test_reasonable_length(self):
        # ISO format: "2024-01-15T12:34:56.789012Z" is 27+ chars
        result = utc_now()
        self.assertGreater(len(result), 20)


# ---------------------------------------------------------------------------
# default_budgets
# ---------------------------------------------------------------------------


class TestDefaultBudgets(unittest.TestCase):
    """Tests for default_budgets() — returns resource-limit dict."""

    def test_returns_dict(self):
        self.assertIsInstance(default_budgets(), dict)

    def test_has_max_wall_time_sec(self):
        self.assertIn("max_wall_time_sec", default_budgets())

    def test_has_max_tool_calls(self):
        self.assertIn("max_tool_calls", default_budgets())

    def test_has_max_output_bytes(self):
        self.assertIn("max_output_bytes", default_budgets())

    def test_has_max_concurrency_slots(self):
        self.assertIn("max_concurrency_slots", default_budgets())

    def test_max_wall_time_is_300(self):
        self.assertEqual(default_budgets()["max_wall_time_sec"], 300)

    def test_max_tool_calls_is_10(self):
        self.assertEqual(default_budgets()["max_tool_calls"], 10)

    def test_max_output_bytes_is_262144(self):
        self.assertEqual(default_budgets()["max_output_bytes"], 262144)

    def test_max_concurrency_slots_is_1(self):
        self.assertEqual(default_budgets()["max_concurrency_slots"], 1)

    def test_returns_new_dict_each_call(self):
        a = default_budgets()
        b = default_budgets()
        self.assertIsNot(a, b)


# ---------------------------------------------------------------------------
# default_tool_policy
# ---------------------------------------------------------------------------


class TestDefaultToolPolicy(unittest.TestCase):
    """Tests for default_tool_policy() — returns tool permission dict."""

    def test_returns_dict(self):
        self.assertIsInstance(default_tool_policy(), dict)

    def test_allow_network_is_false(self):
        self.assertFalse(default_tool_policy()["allow_network"])

    def test_allow_subprocess_default_false(self):
        self.assertFalse(default_tool_policy()["allow_subprocess"])

    def test_allow_subprocess_true_when_passed(self):
        policy = default_tool_policy(allow_subprocess=True)
        self.assertTrue(policy["allow_subprocess"])

    def test_allowed_tools_is_empty_list(self):
        self.assertEqual(default_tool_policy()["allowed_tools"], [])

    def test_has_allow_network_key(self):
        self.assertIn("allow_network", default_tool_policy())

    def test_has_allow_subprocess_key(self):
        self.assertIn("allow_subprocess", default_tool_policy())

    def test_has_allowed_tools_key(self):
        self.assertIn("allowed_tools", default_tool_policy())


# ---------------------------------------------------------------------------
# build_demo_job
# ---------------------------------------------------------------------------


class TestBuildDemoJob(unittest.TestCase):
    """Tests for build_demo_job() — returns a governed job dict."""

    def test_returns_dict(self):
        self.assertIsInstance(build_demo_job(), dict)

    def test_has_job_id(self):
        self.assertIn("job_id", build_demo_job())

    def test_job_id_value(self):
        self.assertEqual(build_demo_job()["job_id"], "job-demorepoindex01")

    def test_has_job_type(self):
        self.assertIn("job_type", build_demo_job())

    def test_job_type_value(self):
        self.assertEqual(build_demo_job()["job_type"], "repo_index_task")

    def test_has_created_at_utc(self):
        self.assertIn("created_at_utc", build_demo_job())

    def test_created_at_utc_ends_z(self):
        self.assertTrue(build_demo_job()["created_at_utc"].endswith("Z"))

    def test_has_payload(self):
        self.assertIn("payload", build_demo_job())

    def test_payload_has_include_globs(self):
        self.assertIn("include_globs", build_demo_job()["payload"])

    def test_payload_include_globs_is_list(self):
        self.assertIsInstance(build_demo_job()["payload"]["include_globs"], list)

    def test_payload_has_keywords(self):
        self.assertIn("keywords", build_demo_job()["payload"])

    def test_has_budgets(self):
        self.assertIn("budgets", build_demo_job())

    def test_budgets_matches_default(self):
        self.assertEqual(build_demo_job()["budgets"], default_budgets())

    def test_has_tool_policy(self):
        self.assertIn("tool_policy", build_demo_job())

    def test_tool_policy_no_subprocess(self):
        self.assertFalse(build_demo_job()["tool_policy"]["allow_subprocess"])

    def test_tool_policy_no_network(self):
        self.assertFalse(build_demo_job()["tool_policy"]["allow_network"])

    def test_has_meta(self):
        self.assertIn("meta", build_demo_job())

    def test_meta_source(self):
        self.assertEqual(build_demo_job()["meta"]["source"], "enqueue-demo")


if __name__ == "__main__":
    unittest.main()
