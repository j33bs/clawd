"""Tests for pure helpers in workspace/router/validate_control_plane.py.

Stubs workspace.agents.control_plane and workspace.models.load_model.

Covers:
- _scenario_prompts
- _count_log_lines
- _find_latest_log_by_reason
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTER_DIR = REPO_ROOT / "workspace" / "router"
WORKSPACE_DIR = REPO_ROOT / "workspace"


def _try_real_import(module_name: str) -> bool:
    """Attempt to import a real module; return True on success."""
    if module_name in sys.modules:
        return True
    try:
        import importlib
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def _ensure_stubs():
    # workspace — prefer real
    if "workspace" not in sys.modules:
        _try_real_import("workspace") or None
        if "workspace" not in sys.modules:
            wp = types.ModuleType("workspace")
            wp.__path__ = [str(WORKSPACE_DIR)]
            wp.__package__ = "workspace"
            sys.modules["workspace"] = wp

    # workspace.agents — prefer real
    if "workspace.agents" not in sys.modules:
        if not _try_real_import("workspace.agents"):
            ag = types.ModuleType("workspace.agents")
            ag.__path__ = [str(WORKSPACE_DIR / "agents")]
            ag.__package__ = "workspace.agents"
            sys.modules["workspace.agents"] = ag

    # workspace.agents.control_plane — prefer real; fall back to stub
    if "workspace.agents.control_plane" not in sys.modules:
        if not _try_real_import("workspace.agents.control_plane"):
            acp = types.ModuleType("workspace.agents.control_plane")
            acp.SmallModelControlPlane = type("SmallModelControlPlane", (), {
                "__init__": lambda self: None,
            })
            sys.modules["workspace.agents.control_plane"] = acp
    else:
        acp = sys.modules["workspace.agents.control_plane"]
        if not hasattr(acp, "SmallModelControlPlane"):
            acp.SmallModelControlPlane = type("SmallModelControlPlane", (), {
                "__init__": lambda self: None,
            })

    # workspace.models — prefer real
    if "workspace.models" not in sys.modules:
        if not _try_real_import("workspace.models"):
            mod = types.ModuleType("workspace.models")
            mod.__path__ = [str(WORKSPACE_DIR / "models")]
            mod.__package__ = "workspace.models"
            sys.modules["workspace.models"] = mod

    # workspace.models.load_model — prefer real; fall back to stub
    if "workspace.models.load_model" not in sys.modules:
        if not _try_real_import("workspace.models.load_model"):
            lm = types.ModuleType("workspace.models.load_model")
            lm.normalize_role_spec = lambda spec, **kw: spec if isinstance(spec, dict) else {}
            sys.modules["workspace.models.load_model"] = lm
    else:
        lm = sys.modules["workspace.models.load_model"]
        if not hasattr(lm, "normalize_role_spec"):
            lm.normalize_role_spec = lambda spec, **kw: spec if isinstance(spec, dict) else {}

    # workspace.router — prefer real
    if "workspace.router" not in sys.modules:
        if not _try_real_import("workspace.router"):
            rt = types.ModuleType("workspace.router")
            rt.__path__ = [str(ROUTER_DIR)]
            rt.__package__ = "workspace.router"
            sys.modules["workspace.router"] = rt


_ensure_stubs()

_spec = _ilu.spec_from_file_location(
    "router_validate_cp_real",
    str(ROUTER_DIR / "validate_control_plane.py"),
)
vc = _ilu.module_from_spec(_spec)
vc.__package__ = "workspace.router"
sys.modules["router_validate_cp_real"] = vc
_spec.loader.exec_module(vc)


# ---------------------------------------------------------------------------
# _scenario_prompts
# ---------------------------------------------------------------------------

class TestScenarioPrompts(unittest.TestCase):
    """Tests for _scenario_prompts() — returns list of scenario dicts."""

    def test_returns_list(self):
        result = vc._scenario_prompts()
        self.assertIsInstance(result, list)

    def test_not_empty(self):
        result = vc._scenario_prompts()
        self.assertGreater(len(result), 0)

    def test_each_has_name(self):
        for scenario in vc._scenario_prompts():
            self.assertIn("name", scenario)

    def test_each_has_prompt(self):
        for scenario in vc._scenario_prompts():
            self.assertIn("prompt", scenario)

    def test_names_are_strings(self):
        for scenario in vc._scenario_prompts():
            self.assertIsInstance(scenario["name"], str)

    def test_prompts_are_strings(self):
        for scenario in vc._scenario_prompts():
            self.assertIsInstance(scenario["prompt"], str)

    def test_has_multiple_scenarios(self):
        # Should have at least 3 scenarios
        result = vc._scenario_prompts()
        self.assertGreaterEqual(len(result), 3)


# ---------------------------------------------------------------------------
# _count_log_lines
# ---------------------------------------------------------------------------

class TestCountLogLines(unittest.TestCase):
    """Tests for _count_log_lines() — counts lines in a file."""

    def test_zero_when_file_missing(self):
        result = vc._count_log_lines(Path("/tmp/nonexistent_log_xyz.jsonl"))
        self.assertEqual(result, 0)

    def test_counts_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                        delete=False, encoding="utf-8") as f:
            f.write('{"a":1}\n{"b":2}\n{"c":3}\n')
            name = f.name
        result = vc._count_log_lines(Path(name))
        self.assertEqual(result, 3)
        import os; os.unlink(name)

    def test_empty_file_returns_zero(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                        delete=False, encoding="utf-8") as f:
            name = f.name
        result = vc._count_log_lines(Path(name))
        self.assertEqual(result, 0)
        import os; os.unlink(name)

    def test_returns_int(self):
        result = vc._count_log_lines(Path("/tmp/nonexistent_xyz.jsonl"))
        self.assertIsInstance(result, int)

    def test_single_line_returns_one(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                        delete=False, encoding="utf-8") as f:
            f.write('{"x":1}\n')
            name = f.name
        result = vc._count_log_lines(Path(name))
        self.assertEqual(result, 1)
        import os; os.unlink(name)


# ---------------------------------------------------------------------------
# _find_latest_log_by_reason
# ---------------------------------------------------------------------------

class TestFindLatestLogByReason(unittest.TestCase):
    """Tests for _find_latest_log_by_reason() — last row matching reason_tag."""

    def _make_log(self, rows):
        """Write rows to a temp file and return its path."""
        import tempfile
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                        delete=False, encoding="utf-8")
        for row in rows:
            f.write(json.dumps(row) + "\n")
        f.close()
        return Path(f.name)

    def test_returns_none_when_file_missing(self):
        result = vc._find_latest_log_by_reason(
            Path("/tmp/nonexistent_xyz.jsonl"), "any_tag"
        )
        self.assertIsNone(result)

    def test_returns_none_when_no_match(self):
        path = self._make_log([{"reason_tag": "other"}])
        result = vc._find_latest_log_by_reason(path, "my_tag")
        self.assertIsNone(result)
        import os; os.unlink(str(path))

    def test_returns_matching_row(self):
        path = self._make_log([{"reason_tag": "my_tag", "val": 1}])
        result = vc._find_latest_log_by_reason(path, "my_tag")
        self.assertIsNotNone(result)
        self.assertEqual(result["val"], 1)
        import os; os.unlink(str(path))

    def test_returns_last_match(self):
        path = self._make_log([
            {"reason_tag": "my_tag", "val": 1},
            {"reason_tag": "other", "val": 9},
            {"reason_tag": "my_tag", "val": 2},
        ])
        result = vc._find_latest_log_by_reason(path, "my_tag")
        self.assertEqual(result["val"], 2)  # last match
        import os; os.unlink(str(path))

    def test_skips_invalid_json(self):
        import tempfile
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                        delete=False, encoding="utf-8")
        f.write('NOT JSON\n')
        f.write(json.dumps({"reason_tag": "my_tag", "val": 3}) + "\n")
        f.close()
        result = vc._find_latest_log_by_reason(Path(f.name), "my_tag")
        self.assertIsNotNone(result)
        self.assertEqual(result["val"], 3)
        import os; os.unlink(f.name)

    def test_returns_dict(self):
        path = self._make_log([{"reason_tag": "tag1", "k": "v"}])
        result = vc._find_latest_log_by_reason(path, "tag1")
        self.assertIsInstance(result, dict)
        import os; os.unlink(str(path))


if __name__ == "__main__":
    unittest.main()
