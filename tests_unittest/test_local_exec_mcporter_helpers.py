"""Tests for pure helpers in workspace/local_exec/tools_mcporter.py.

Stubs local_exec.evidence (append_worker_event).
Tests load/config, enabled_tools, command_path, and call_tool guard logic.

Covers:
- MCPorterAdapter._load_config
- MCPorterAdapter.enabled_tools
- MCPorterAdapter.command_path (static)
- MCPorterAdapter.call_tool (guard paths only — no real subprocess)
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_EXEC_DIR = REPO_ROOT / "workspace" / "local_exec"


def _ensure_local_exec_pkg():
    if "local_exec" not in sys.modules:
        pkg = types.ModuleType("local_exec")
        pkg.__path__ = [str(LOCAL_EXEC_DIR)]
        pkg.__package__ = "local_exec"
        sys.modules["local_exec"] = pkg

    if "local_exec.evidence" not in sys.modules:
        ev = types.ModuleType("local_exec.evidence")
        ev.append_worker_event = lambda *a, **kw: None
        sys.modules["local_exec.evidence"] = ev
        setattr(sys.modules["local_exec"], "evidence", ev)
    else:
        ev = sys.modules["local_exec.evidence"]
        if not hasattr(ev, "append_worker_event"):
            ev.append_worker_event = lambda *a, **kw: None


_ensure_local_exec_pkg()

_spec = _ilu.spec_from_file_location(
    "local_exec_mcporter_real",
    str(LOCAL_EXEC_DIR / "tools_mcporter.py"),
)
mc = _ilu.module_from_spec(_spec)
mc.__package__ = "local_exec"
sys.modules["local_exec_mcporter_real"] = mc
_spec.loader.exec_module(mc)


def _make_adapter(tmp: str, config: dict | None = None) -> "mc.MCPorterAdapter":
    """Create adapter, optionally writing a config file."""
    root = Path(tmp)
    if config is not None:
        config_path = root / "config" / "mcporter.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config), encoding="utf-8")
    return mc.MCPorterAdapter(repo_root=root)


# ---------------------------------------------------------------------------
# _load_config
# ---------------------------------------------------------------------------

class TestLoadConfig(unittest.TestCase):
    """Tests for MCPorterAdapter._load_config() — reads or returns default."""

    def test_default_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _make_adapter(tmp)
            self.assertIn("enabled_tools", adapter._cfg)

    def test_default_enabled_tools_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _make_adapter(tmp)
            self.assertEqual(adapter._cfg["enabled_tools"], [])

    def test_loads_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {"enabled_tools": ["mytool"], "timeout_sec": 60, "max_response_bytes": 65536}
            adapter = _make_adapter(tmp, config=config)
            self.assertIn("mytool", adapter._cfg["enabled_tools"])

    def test_timeout_clamped_max(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {"enabled_tools": [], "timeout_sec": 9999}
            adapter = _make_adapter(tmp, config=config)
            self.assertLessEqual(adapter._cfg["timeout_sec"], 300)

    def test_timeout_clamped_min(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {"enabled_tools": [], "timeout_sec": 0}
            adapter = _make_adapter(tmp, config=config)
            self.assertGreaterEqual(adapter._cfg["timeout_sec"], 1)

    def test_max_response_bytes_clamped(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {"enabled_tools": [], "max_response_bytes": 99999999}
            adapter = _make_adapter(tmp, config=config)
            self.assertLessEqual(adapter._cfg["max_response_bytes"], 1048576)

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cp = root / "config" / "mcporter.json"
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text("NOT JSON", encoding="utf-8")
            with self.assertRaises(mc.MCPorterError):
                mc.MCPorterAdapter(repo_root=root)

    def test_invalid_enabled_tools_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {"enabled_tools": "not-a-list"}
            with self.assertRaises(mc.MCPorterError):
                _make_adapter(tmp, config=config)


# ---------------------------------------------------------------------------
# enabled_tools property
# ---------------------------------------------------------------------------

class TestEnabledTools(unittest.TestCase):
    """Tests for MCPorterAdapter.enabled_tools — set from config."""

    def test_returns_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _make_adapter(tmp)
            self.assertIsInstance(adapter.enabled_tools, set)

    def test_empty_when_no_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _make_adapter(tmp)
            self.assertEqual(adapter.enabled_tools, set())

    def test_contains_configured_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {"enabled_tools": ["tool_a", "tool_b"]}
            adapter = _make_adapter(tmp, config=config)
            self.assertIn("tool_a", adapter.enabled_tools)
            self.assertIn("tool_b", adapter.enabled_tools)


# ---------------------------------------------------------------------------
# command_path (static)
# ---------------------------------------------------------------------------

class TestCommandPath(unittest.TestCase):
    """Tests for MCPorterAdapter.command_path() — shutil.which result."""

    def test_returns_none_when_not_found(self):
        with patch("shutil.which", return_value=None):
            result = mc.MCPorterAdapter.command_path()
        self.assertIsNone(result)

    def test_returns_path_when_found(self):
        with patch("shutil.which", return_value="/usr/local/bin/mcporter"):
            result = mc.MCPorterAdapter.command_path()
        self.assertEqual(result, "/usr/local/bin/mcporter")


# ---------------------------------------------------------------------------
# call_tool guard paths
# ---------------------------------------------------------------------------

class TestCallToolGuards(unittest.TestCase):
    """Tests for MCPorterAdapter.call_tool() guard paths (no subprocess)."""

    def test_raises_when_tool_not_allowlisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _make_adapter(tmp)  # empty allowlist
            with self.assertRaises(mc.MCPorterError):
                adapter.call_tool("some_tool", {})

    def test_raises_correct_error_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _make_adapter(tmp)
            try:
                adapter.call_tool("unapproved_tool", {})
                self.fail("Expected MCPorterError")
            except mc.MCPorterError as e:
                self.assertIn("unapproved_tool", str(e))

    def test_payload_must_be_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {"enabled_tools": ["allowed_tool"]}
            adapter = _make_adapter(tmp, config=config)
            # Make it think mcporter is available but payload invalid
            with patch.object(mc.MCPorterAdapter, "is_available", return_value=True):
                with self.assertRaises(mc.MCPorterError):
                    adapter.call_tool("allowed_tool", "not-a-dict")

    def test_raises_when_mcporter_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {"enabled_tools": ["mytool"]}
            adapter = _make_adapter(tmp, config=config)
            with patch.object(mc.MCPorterAdapter, "is_available", return_value=False):
                with self.assertRaises(mc.MCPorterError):
                    adapter.call_tool("mytool", {})


if __name__ == "__main__":
    unittest.main()
