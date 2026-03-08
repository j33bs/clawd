"""Tests for pure helpers in workspace/agents/control_plane.py.

Stubs workspace.agents.hint_engine, workspace.agents.prompt_compressor,
workspace.models.load_model, workspace.router.router so no real model
calls occur at import time.

Covers:
- SmallModelControlPlane._predict_budget (static)
- SmallModelControlPlane._acc_usage (static)
- SmallModelControlPlane._append_jsonl (static)
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "workspace" / "agents"
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


def _ensure_workspace_pkg_stubs():
    """Install workspace package hierarchy; prefer real modules over stubs."""
    # workspace package — try real first, then stub
    if "workspace" not in sys.modules:
        if not _try_real_import("workspace"):
            wp = types.ModuleType("workspace")
            wp.__path__ = [str(WORKSPACE_DIR)]
            wp.__package__ = "workspace"
            sys.modules["workspace"] = wp

    # workspace.agents
    if "workspace.agents" not in sys.modules:
        if not _try_real_import("workspace.agents"):
            ag = types.ModuleType("workspace.agents")
            ag.__path__ = [str(AGENTS_DIR)]
            ag.__package__ = "workspace.agents"
            sys.modules["workspace.agents"] = ag
            setattr(sys.modules["workspace"], "agents", ag)

    # workspace.agents.hint_engine — try real, fall back to minimal stub
    if "workspace.agents.hint_engine" not in sys.modules:
        if not _try_real_import("workspace.agents.hint_engine"):
            he = types.ModuleType("workspace.agents.hint_engine")
            he.HintEngine = type("HintEngine", (), {
                "__init__": lambda self: None,
                "request_hint": lambda self, *a, **kw: {"hint": ""},
                "request_completion_fallback": lambda self, *a, **kw: {"status": "error"},
            })
            sys.modules["workspace.agents.hint_engine"] = he

    # workspace.agents.prompt_compressor — try real, fall back to stub
    if "workspace.agents.prompt_compressor" not in sys.modules:
        if not _try_real_import("workspace.agents.prompt_compressor"):
            pc = types.ModuleType("workspace.agents.prompt_compressor")
            pc.compress_prompt = lambda text, max_chars=7000: {
                "text": str(text)[:max_chars],
                "compressed": False,
                "original_chars": len(str(text)),
                "compressed_chars": len(str(text)),
            }
            sys.modules["workspace.agents.prompt_compressor"] = pc

    # workspace.models
    if "workspace.models" not in sys.modules:
        if not _try_real_import("workspace.models"):
            mod = types.ModuleType("workspace.models")
            mod.__path__ = [str(WORKSPACE_DIR / "models")]
            mod.__package__ = "workspace.models"
            sys.modules["workspace.models"] = mod
            setattr(sys.modules["workspace"], "models", mod)

    # workspace.models.load_model — try real, fall back to stub
    if "workspace.models.load_model" not in sys.modules:
        if not _try_real_import("workspace.models.load_model"):
            ll = types.ModuleType("workspace.models.load_model")
            ll.ModelLoader = type("ModelLoader", (), {
                "__init__": lambda self, **kw: None,
                "registry": {},
            })
            sys.modules["workspace.models.load_model"] = ll

    # workspace.router
    if "workspace.router" not in sys.modules:
        if not _try_real_import("workspace.router"):
            rt = types.ModuleType("workspace.router")
            rt.__path__ = [str(WORKSPACE_DIR / "router")]
            rt.__package__ = "workspace.router"
            sys.modules["workspace.router"] = rt
            setattr(sys.modules["workspace"], "router", rt)

    # workspace.router.router — try real, fall back to stub
    if "workspace.router.router" not in sys.modules:
        if not _try_real_import("workspace.router.router"):
            rr = types.ModuleType("workspace.router.router")
            rr.SmallModelRouter = type("SmallModelRouter", (), {
                "__init__": lambda self, **kw: None,
            })
            sys.modules["workspace.router.router"] = rr


_ensure_workspace_pkg_stubs()

_spec = _ilu.spec_from_file_location(
    "agents_control_plane_real",
    str(AGENTS_DIR / "control_plane.py"),
)
cp = _ilu.module_from_spec(_spec)
cp.__package__ = "workspace.agents"
sys.modules["agents_control_plane_real"] = cp
_spec.loader.exec_module(cp)

SMCP = cp.SmallModelControlPlane


# ---------------------------------------------------------------------------
# _predict_budget
# ---------------------------------------------------------------------------

class TestPredictBudget(unittest.TestCase):
    """Tests for SmallModelControlPlane._predict_budget() — expert token budgets."""

    def test_general_base(self):
        result = SMCP._predict_budget("general")
        self.assertEqual(result, 220)

    def test_knowledge_base(self):
        result = SMCP._predict_budget("knowledge")
        self.assertEqual(result, 240)

    def test_reasoning_base(self):
        result = SMCP._predict_budget("reasoning")
        self.assertEqual(result, 320)

    def test_automation_base(self):
        result = SMCP._predict_budget("automation")
        self.assertEqual(result, 260)

    def test_unknown_expert_defaults_240(self):
        result = SMCP._predict_budget("unknown_expert")
        self.assertEqual(result, 240)

    def test_shepherded_adds_80(self):
        base = SMCP._predict_budget("general", shepherded=False)
        shep = SMCP._predict_budget("general", shepherded=True)
        self.assertEqual(shep, base + 80)

    def test_returns_int(self):
        result = SMCP._predict_budget("reasoning")
        self.assertIsInstance(result, int)

    def test_shepherded_false_default(self):
        # Default shepherded=False
        result = SMCP._predict_budget("knowledge")
        self.assertEqual(result, 240)


# ---------------------------------------------------------------------------
# _acc_usage
# ---------------------------------------------------------------------------

class TestAccUsage(unittest.TestCase):
    """Tests for SmallModelControlPlane._acc_usage() — accumulates token counts."""

    def _empty_target(self):
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def test_accumulates_input_tokens(self):
        target = self._empty_target()
        SMCP._acc_usage(target, {"input_tokens": 10})
        self.assertEqual(target["input_tokens"], 10)

    def test_accumulates_output_tokens(self):
        target = self._empty_target()
        SMCP._acc_usage(target, {"output_tokens": 5})
        self.assertEqual(target["output_tokens"], 5)

    def test_accumulates_total_tokens(self):
        target = self._empty_target()
        SMCP._acc_usage(target, {"total_tokens": 15})
        self.assertEqual(target["total_tokens"], 15)

    def test_empty_usage_no_change(self):
        target = self._empty_target()
        SMCP._acc_usage(target, {})
        self.assertEqual(target, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})

    def test_cumulative(self):
        target = self._empty_target()
        SMCP._acc_usage(target, {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5})
        SMCP._acc_usage(target, {"input_tokens": 7, "output_tokens": 8, "total_tokens": 15})
        self.assertEqual(target["input_tokens"], 10)
        self.assertEqual(target["output_tokens"], 10)
        self.assertEqual(target["total_tokens"], 20)

    def test_none_treated_as_zero(self):
        target = self._empty_target()
        SMCP._acc_usage(target, {"input_tokens": None, "output_tokens": None, "total_tokens": None})
        self.assertEqual(target["input_tokens"], 0)


# ---------------------------------------------------------------------------
# _append_jsonl
# ---------------------------------------------------------------------------

class TestAppendJsonl(unittest.TestCase):
    """Tests for SmallModelControlPlane._append_jsonl() — creates parents and appends."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "log.jsonl"
            SMCP._append_jsonl(path, {"key": "value"})
            self.assertTrue(path.exists())

    def test_creates_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a" / "b" / "log.jsonl"
            SMCP._append_jsonl(path, {"x": 1})
            self.assertTrue(path.parent.exists())

    def test_content_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "log.jsonl"
            SMCP._append_jsonl(path, {"answer": 42})
            line = path.read_text(encoding="utf-8").strip()
            obj = json.loads(line)
            self.assertEqual(obj["answer"], 42)

    def test_appends_multiple_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "log.jsonl"
            SMCP._append_jsonl(path, {"n": 1})
            SMCP._append_jsonl(path, {"n": 2})
            lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(len(lines), 2)

    def test_sorted_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "log.jsonl"
            SMCP._append_jsonl(path, {"z": 3, "a": 1})
            line = path.read_text(encoding="utf-8").strip()
            # sort_keys=True means "a" comes before "z" in the output
            self.assertLess(line.index('"a"'), line.index('"z"'))


if __name__ == "__main__":
    unittest.main()
