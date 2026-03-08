"""Tests for pure helpers in workspace/tacti/valence.py.

Stubs tacti.config (get_float, is_enabled) and tacti.events (emit).
Covers the pure stdlib helpers and the high-level functions via patching.

Covers:
- _state_path
- _now
- _load
- _save
- current_valence (with is_enabled=True stub)
- routing_bias
"""
import importlib.util as _ilu
import json
import math
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
TACTI_DIR = REPO_ROOT / "workspace" / "tacti"


def _ensure_tacti_pkg():
    if "tacti" not in sys.modules:
        pkg = types.ModuleType("tacti")
        pkg.__path__ = [str(TACTI_DIR)]
        pkg.__package__ = "tacti"
        sys.modules["tacti"] = pkg

    # tacti.config stub
    if "tacti.config" not in sys.modules:
        cfg = types.ModuleType("tacti.config")
        cfg.get_float = lambda name, default, clamp=None, **kw: default
        cfg.is_enabled = lambda name, default=True: True
        sys.modules["tacti.config"] = cfg
        setattr(sys.modules["tacti"], "config", cfg)
    else:
        cfg = sys.modules["tacti.config"]
        if not hasattr(cfg, "get_float"):
            cfg.get_float = lambda name, default, clamp=None, **kw: default
        if not hasattr(cfg, "is_enabled"):
            cfg.is_enabled = lambda name, default=True: True

    # tacti.events stub
    if "tacti.events" not in sys.modules:
        ev = types.ModuleType("tacti.events")
        ev.emit = lambda *a, **kw: None
        sys.modules["tacti.events"] = ev
        setattr(sys.modules["tacti"], "events", ev)
    else:
        ev = sys.modules["tacti.events"]
        if not hasattr(ev, "emit"):
            ev.emit = lambda *a, **kw: None


_ensure_tacti_pkg()

_spec = _ilu.spec_from_file_location("tacti_valence_real", str(TACTI_DIR / "valence.py"))
val = _ilu.module_from_spec(_spec)
val.__package__ = "tacti"
sys.modules["tacti_valence_real"] = val
_spec.loader.exec_module(val)


# ---------------------------------------------------------------------------
# _state_path
# ---------------------------------------------------------------------------

class TestStatePath(unittest.TestCase):
    """Tests for _state_path() — pure path computation."""

    def test_returns_path(self):
        result = val._state_path("myagent")
        self.assertIsInstance(result, Path)

    def test_contains_agent_name(self):
        result = val._state_path("c_lawd")
        self.assertIn("c_lawd", result.name)

    def test_json_extension(self):
        result = val._state_path("dali")
        self.assertEqual(result.suffix, ".json")

    def test_uses_repo_root_override(self):
        result = val._state_path("agent", repo_root=Path("/tmp/fakerepo"))
        self.assertTrue(str(result).startswith("/tmp/fakerepo"))

    def test_under_workspace_state_valence(self):
        result = val._state_path("agent", repo_root=Path("/tmp/r"))
        parts = result.parts
        self.assertIn("workspace", parts)
        self.assertIn("state", parts)
        self.assertIn("valence", parts)


# ---------------------------------------------------------------------------
# _now
# ---------------------------------------------------------------------------

class TestNow(unittest.TestCase):
    """Tests for _now() — UTC datetime with timezone."""

    def test_returns_datetime(self):
        result = val._now()
        self.assertIsInstance(result, datetime)

    def test_has_tzinfo(self):
        result = val._now()
        self.assertIsNotNone(result.tzinfo)

    def test_naive_datetime_gets_utc(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        result = val._now(naive)
        self.assertIsNotNone(result.tzinfo)

    def test_aware_datetime_returned_unchanged_tzinfo(self):
        aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = val._now(aware)
        self.assertIsNotNone(result.tzinfo)

    def test_none_returns_current_time(self):
        before = datetime.now(timezone.utc)
        result = val._now(None)
        after = datetime.now(timezone.utc)
        self.assertGreaterEqual(result, before)
        self.assertLessEqual(result, after)


# ---------------------------------------------------------------------------
# _load
# ---------------------------------------------------------------------------

class TestLoad(unittest.TestCase):
    """Tests for _load() — reads JSON or returns default."""

    def test_missing_file_returns_default(self):
        path = Path("/tmp/nonexistent_valence_xyz.json")
        result = val._load(path)
        self.assertIsInstance(result, dict)
        self.assertIn("valence", result)

    def test_valid_file_loaded(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w",
                                        delete=False, encoding="utf-8") as f:
            json.dump({"valence": 0.5, "updated_at": "2026-01-01T00:00:00Z"}, f)
            name = f.name
        result = val._load(Path(name))
        self.assertAlmostEqual(result["valence"], 0.5)
        import os; os.unlink(name)

    def test_invalid_json_returns_default(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w",
                                        delete=False, encoding="utf-8") as f:
            f.write("NOT JSON {{}")
            name = f.name
        result = val._load(Path(name))
        self.assertIn("valence", result)
        import os; os.unlink(name)

    def test_default_valence_zero(self):
        result = val._load(Path("/tmp/no_such_file_xyz.json"))
        self.assertEqual(result["valence"], 0.0)


# ---------------------------------------------------------------------------
# _save
# ---------------------------------------------------------------------------

class TestSave(unittest.TestCase):
    """Tests for _save() — writes JSON to path, creates parents."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "agent.json"
            val._save(path, {"valence": 0.3})
            self.assertTrue(path.exists())

    def test_content_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agent.json"
            val._save(path, {"valence": 0.7, "agent": "dali"})
            obj = json.loads(path.read_text(encoding="utf-8"))
            self.assertAlmostEqual(obj["valence"], 0.7)

    def test_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a" / "b" / "c" / "agent.json"
            val._save(path, {"valence": 0.0})
            self.assertTrue(path.parent.exists())


# ---------------------------------------------------------------------------
# current_valence
# ---------------------------------------------------------------------------

class TestCurrentValence(unittest.TestCase):
    """Tests for current_valence() — decayed valence read from store."""

    def test_returns_float_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(val, "is_enabled", return_value=True):
                result = val.current_valence("test_agent", repo_root=Path(tmp))
            self.assertIsInstance(result, float)

    def test_returns_zero_when_disabled(self):
        with patch.object(val, "is_enabled", return_value=False):
            result = val.current_valence("test_agent")
        self.assertEqual(result, 0.0)

    def test_bounded_between_neg1_and_pos1(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(val, "is_enabled", return_value=True):
                result = val.current_valence("test_agent", repo_root=Path(tmp))
            self.assertGreaterEqual(result, -1.0)
            self.assertLessEqual(result, 1.0)

    def test_fresh_state_returns_zero(self):
        # No prior state file → valence=0.0 decays to 0.0
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(val, "is_enabled", return_value=True):
                with patch.object(val, "get_float", return_value=6.0):
                    result = val.current_valence("nofile", repo_root=Path(tmp))
            self.assertAlmostEqual(result, 0.0)


# ---------------------------------------------------------------------------
# routing_bias
# ---------------------------------------------------------------------------

class TestRoutingBias(unittest.TestCase):
    """Tests for routing_bias() — dict with routing signals."""

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(val, "is_enabled", return_value=False):
                result = val.routing_bias("agent", repo_root=Path(tmp))
            self.assertIsInstance(result, dict)

    def test_contains_valence_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(val, "is_enabled", return_value=False):
                result = val.routing_bias("agent", repo_root=Path(tmp))
            self.assertIn("valence", result)

    def test_contains_prefer_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(val, "is_enabled", return_value=False):
                result = val.routing_bias("agent", repo_root=Path(tmp))
            self.assertIn("prefer_local", result)

    def test_contains_tighten_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(val, "is_enabled", return_value=False):
                result = val.routing_bias("agent", repo_root=Path(tmp))
            self.assertIn("tighten_budget", result)

    def test_contains_exploration_bias(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(val, "is_enabled", return_value=False):
                result = val.routing_bias("agent", repo_root=Path(tmp))
            self.assertIn("exploration_bias", result)

    def test_prefer_local_false_at_zero_valence(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(val, "is_enabled", return_value=False):
                result = val.routing_bias("agent", repo_root=Path(tmp))
            # valence=0.0 => prefer_local = 0.0 < -0.2 => False
            self.assertFalse(result["prefer_local"])


if __name__ == "__main__":
    unittest.main()
