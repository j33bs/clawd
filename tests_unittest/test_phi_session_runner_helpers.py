"""Tests for pure helpers in workspace/scripts/phi_session_runner.py.

Skips _commit_sha (subprocess) and _module_statuses (imports hivemind pipeline).
Tests only the stdlib-only pure helpers.

Covers:
- _utc_now
- _detect_node
- _write_snapshot
"""
import importlib.util as _ilu
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"

# phi_session_runner adds workspace/hivemind to sys.path and tries to import
# from hivemind.dynamics_pipeline inside _module_statuses — but that's a lazy
# import so it won't run at module load time. No stubs needed.
_spec = _ilu.spec_from_file_location(
    "phi_session_runner_real",
    str(SCRIPTS_DIR / "phi_session_runner.py"),
)
phi = _ilu.module_from_spec(_spec)
sys.modules["phi_session_runner_real"] = phi
_spec.loader.exec_module(phi)


# ---------------------------------------------------------------------------
# _utc_now
# ---------------------------------------------------------------------------

class TestUtcNow(unittest.TestCase):
    """Tests for _utc_now() — UTC ISO string with Z suffix, no microseconds."""

    def test_returns_string(self):
        self.assertIsInstance(phi._utc_now(), str)

    def test_ends_with_z(self):
        self.assertTrue(phi._utc_now().endswith("Z"))

    def test_no_microseconds(self):
        # replace(microsecond=0) means no fractional seconds
        result = phi._utc_now()
        self.assertNotIn(".", result)

    def test_parseable(self):
        result = phi._utc_now()
        datetime.fromisoformat(result.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# _detect_node
# ---------------------------------------------------------------------------

class TestDetectNode(unittest.TestCase):
    """Tests for _detect_node() — reads OPENCLAW_NODE_ID or defaults."""

    def test_default_when_unset(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_NODE_ID"}
        with patch.dict(os.environ, env, clear=True):
            result = phi._detect_node()
            self.assertEqual(result, "Dali/C_Lawd")

    def test_env_override(self):
        with patch.dict(os.environ, {"OPENCLAW_NODE_ID": "custom-node"}):
            result = phi._detect_node()
            self.assertEqual(result, "custom-node")

    def test_returns_string(self):
        self.assertIsInstance(phi._detect_node(), str)


# ---------------------------------------------------------------------------
# _write_snapshot
# ---------------------------------------------------------------------------

class TestWriteSnapshot(unittest.TestCase):
    """Tests for _write_snapshot() — writes JSON snapshot to phi_sessions/."""

    def _patch_repo_root(self, tmp: str):
        """Patch REPO_ROOT so snapshot writes to temp dir."""
        return patch.object(phi, "REPO_ROOT", Path(tmp))

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self._patch_repo_root(tmp):
                result = phi._write_snapshot("20260307T120000Z", {"x": 1})
                self.assertIsInstance(result, Path)

    def test_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self._patch_repo_root(tmp):
                path = phi._write_snapshot("20260307T120000Z", {"key": "value"})
                self.assertTrue(path.exists())

    def test_valid_json_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self._patch_repo_root(tmp):
                path = phi._write_snapshot("20260307T120000Z", {"answer": 42})
                obj = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(obj["answer"], 42)

    def test_filename_includes_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self._patch_repo_root(tmp):
                path = phi._write_snapshot("20260307T120000Z", {})
                self.assertIn("20260307T120000Z", path.name)

    def test_in_phi_sessions_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self._patch_repo_root(tmp):
                path = phi._write_snapshot("20260307T120000Z", {})
                self.assertIn("phi_sessions", str(path))


if __name__ == "__main__":
    unittest.main()
