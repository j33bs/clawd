"""Tests for pure helpers in workspace/hivemind/hivemind/integrations/main_flow_hook.py.

Requires stubs for ..dynamics_pipeline and ..flags relative imports.
Only tests the stdlib-only pure functions; skips _pipeline_for, resolve_agent_ids,
and other functions that actually use TactiDynamicsPipeline.

Covers:
- _unique
- _sorted_unique
- _read_json
- _expand_policy_order
- stable_seed
- dynamics_flags_enabled (mocked env)
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HM_DIR = REPO_ROOT / "workspace" / "hivemind" / "hivemind"
INTEGRATIONS_DIR = HM_DIR / "integrations"


# ---------------------------------------------------------------------------
# Set up package hierarchy + stubs
# ---------------------------------------------------------------------------

def _ensure_pkg(name: str, path: str):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.__path__ = [path]
        mod.__package__ = name
        sys.modules[name] = mod
    return sys.modules[name]

def _ensure_hivemind_pkgs():
    hm = _ensure_pkg("hivemind", str(HM_DIR.parent))
    hm_hm = _ensure_pkg("hivemind.hivemind", str(HM_DIR))
    setattr(hm, "hivemind", hm_hm)
    hm_int = _ensure_pkg("hivemind.hivemind.integrations", str(INTEGRATIONS_DIR))
    setattr(hm_hm, "integrations", hm_int)

def _ensure_dynamics_stub():
    key = "hivemind.hivemind.dynamics_pipeline"
    if key not in sys.modules:
        mod = types.ModuleType(key)

        class TactiDynamicsPipeline:
            def __init__(self, *, agent_ids=None, seed=0):
                self.agent_ids = list(agent_ids or [])
            def snapshot(self):
                return {"flags": {}}
            @classmethod
            def load(cls, payload):
                ids = payload.get("agent_ids", [])
                return cls(agent_ids=ids)

        mod.TactiDynamicsPipeline = TactiDynamicsPipeline
        sys.modules[key] = mod
        setattr(sys.modules["hivemind.hivemind"], "dynamics_pipeline", mod)

def _ensure_flags_stub():
    key = "hivemind.hivemind.flags"
    if key not in sys.modules:
        mod = types.ModuleType(key)
        mod.TACTI_DYNAMICS_FLAGS = ("ENABLE_RESERVOIR", "ENABLE_MURMURATION")
        mod.any_enabled = lambda names, environ=None: any(
            str((environ or {}).get(n, "0")).strip() == "1" for n in names
        )
        sys.modules[key] = mod
        setattr(sys.modules["hivemind.hivemind"], "flags", mod)


_ensure_hivemind_pkgs()
_ensure_dynamics_stub()
_ensure_flags_stub()

_spec = _ilu.spec_from_file_location(
    "hivemind.hivemind.integrations.main_flow_hook",
    str(INTEGRATIONS_DIR / "main_flow_hook.py"),
)
hook = _ilu.module_from_spec(_spec)
hook.__package__ = "hivemind.hivemind.integrations"
sys.modules["hivemind.hivemind.integrations.main_flow_hook"] = hook
_spec.loader.exec_module(hook)


# ---------------------------------------------------------------------------
# _unique
# ---------------------------------------------------------------------------

class TestUnique(unittest.TestCase):
    """Tests for _unique() — deduplication preserving insertion order."""

    def test_duplicates_removed(self):
        result = hook._unique(["a", "b", "a", "c"])
        self.assertEqual(result, ["a", "b", "c"])

    def test_order_preserved(self):
        result = hook._unique(["b", "a", "c"])
        self.assertEqual(result, ["b", "a", "c"])

    def test_empty_strings_excluded(self):
        result = hook._unique(["", "a", "  "])
        self.assertNotIn("", result)

    def test_returns_list(self):
        self.assertIsInstance(hook._unique(["x"]), list)

    def test_whitespace_stripped(self):
        result = hook._unique(["  hello  "])
        self.assertEqual(result, ["hello"])


# ---------------------------------------------------------------------------
# _sorted_unique
# ---------------------------------------------------------------------------

class TestSortedUnique(unittest.TestCase):
    """Tests for _sorted_unique() — sorted deduplication."""

    def test_sorted_output(self):
        result = hook._sorted_unique(["b", "a", "c"])
        self.assertEqual(result, ["a", "b", "c"])

    def test_duplicates_removed(self):
        result = hook._sorted_unique(["a", "a", "b"])
        self.assertEqual(result, ["a", "b"])

    def test_empty_list(self):
        self.assertEqual(hook._sorted_unique([]), [])


# ---------------------------------------------------------------------------
# _read_json
# ---------------------------------------------------------------------------

class TestReadJson(unittest.TestCase):
    """Tests for _read_json() — reads JSON dict from file."""

    def test_valid_json_dict_returned(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"key": "value"}, f)
            fname = f.name
        result = hook._read_json(Path(fname))
        self.assertEqual(result["key"], "value")

    def test_missing_file_returns_empty_dict(self):
        result = hook._read_json(Path("/nonexistent/path.json"))
        self.assertEqual(result, {})

    def test_invalid_json_returns_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write("not json")
            fname = f.name
        result = hook._read_json(Path(fname))
        self.assertEqual(result, {})

    def test_non_dict_json_returns_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump([1, 2, 3], f)
            fname = f.name
        result = hook._read_json(Path(fname))
        self.assertEqual(result, {})

    def test_returns_dict(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"x": 1}, f)
            fname = f.name
        result = hook._read_json(Path(fname))
        self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# _expand_policy_order
# ---------------------------------------------------------------------------

class TestExpandPolicyOrder(unittest.TestCase):
    """Tests for _expand_policy_order() — resolves 'free' placeholder."""

    def test_literal_names_passed_through(self):
        result = hook._expand_policy_order(
            {"routing": {"free_order": []}},
            ["agent_a", "agent_b"],
        )
        self.assertEqual(result, ["agent_a", "agent_b"])

    def test_free_expanded(self):
        policy = {"routing": {"free_order": ["x", "y"]}}
        result = hook._expand_policy_order(policy, ["free"])
        self.assertIn("x", result)
        self.assertIn("y", result)

    def test_empty_order_returns_empty(self):
        result = hook._expand_policy_order({}, [])
        self.assertEqual(result, [])

    def test_duplicates_removed(self):
        result = hook._expand_policy_order({}, ["a", "a", "b"])
        self.assertEqual(result.count("a"), 1)


# ---------------------------------------------------------------------------
# stable_seed
# ---------------------------------------------------------------------------

class TestStableSeed(unittest.TestCase):
    """Tests for stable_seed() — deterministic int from agent IDs + session."""

    def test_returns_int(self):
        result = hook.stable_seed(["agent_a", "agent_b"])
        self.assertIsInstance(result, int)

    def test_deterministic(self):
        a = hook.stable_seed(["x", "y"], session_id="s1")
        b = hook.stable_seed(["x", "y"], session_id="s1")
        self.assertEqual(a, b)

    def test_order_invariant(self):
        # Sorted unique → order-invariant
        a = hook.stable_seed(["b", "a"])
        b = hook.stable_seed(["a", "b"])
        self.assertEqual(a, b)

    def test_different_sessions_differ(self):
        a = hook.stable_seed(["x"], session_id="s1")
        b = hook.stable_seed(["x"], session_id="s2")
        self.assertNotEqual(a, b)

    def test_non_negative(self):
        result = hook.stable_seed(["agent_a"])
        self.assertGreaterEqual(result, 0)


# ---------------------------------------------------------------------------
# dynamics_flags_enabled
# ---------------------------------------------------------------------------

class TestDynamicsFlagsEnabled(unittest.TestCase):
    """Tests for dynamics_flags_enabled() — any flag in TACTI_DYNAMICS_FLAGS set."""

    def test_no_flags_returns_false(self):
        result = hook.dynamics_flags_enabled(environ={})
        self.assertFalse(result)

    def test_one_flag_set_returns_true(self):
        result = hook.dynamics_flags_enabled(environ={"ENABLE_RESERVOIR": "1"})
        self.assertTrue(result)

    def test_returns_bool(self):
        result = hook.dynamics_flags_enabled(environ={})
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
