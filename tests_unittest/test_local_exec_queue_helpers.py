"""Tests for pure helpers in workspace/local_exec/queue.py.

Stubs the .validation relative import and tests only the pure
module-level helpers (no file locking, no enqueue logic).

Covers:
- _utc_now
- _state_dir
- ledger_path
- lock_path
- _append_event
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
LOCAL_EXEC_DIR = REPO_ROOT / "workspace" / "local_exec"

# ---------------------------------------------------------------------------
# Stub .validation relative import
# ---------------------------------------------------------------------------

def _ensure_local_exec_pkg():
    if "local_exec" not in sys.modules:
        pkg = types.ModuleType("local_exec")
        pkg.__path__ = [str(LOCAL_EXEC_DIR)]
        pkg.__package__ = "local_exec"
        sys.modules["local_exec"] = pkg

def _ensure_validation_stub():
    if "local_exec.validation" not in sys.modules:
        mod = types.ModuleType("local_exec.validation")
        mod.validate_job = lambda job: None
        mod.validate_payload_for_job_type = lambda job_type, payload: None
        mod.validator_mode = lambda: "lite"
        sys.modules["local_exec.validation"] = mod
        setattr(sys.modules["local_exec"], "validation", mod)


_ensure_local_exec_pkg()
_ensure_validation_stub()

_spec = _ilu.spec_from_file_location(
    "local_exec.queue",
    str(LOCAL_EXEC_DIR / "queue.py"),
)
queue = _ilu.module_from_spec(_spec)
queue.__package__ = "local_exec"
sys.modules["local_exec.queue"] = queue
_spec.loader.exec_module(queue)


# ---------------------------------------------------------------------------
# _utc_now
# ---------------------------------------------------------------------------

class TestUtcNow(unittest.TestCase):
    """Tests for _utc_now() — UTC ISO string ending with Z."""

    def test_returns_string(self):
        self.assertIsInstance(queue._utc_now(), str)

    def test_ends_with_z(self):
        self.assertTrue(queue._utc_now().endswith("Z"))

    def test_parseable(self):
        result = queue._utc_now()
        datetime.fromisoformat(result.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# _state_dir
# ---------------------------------------------------------------------------

class TestStateDir(unittest.TestCase):
    """Tests for _state_dir() — returns and creates state directory."""

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = queue._state_dir(Path(tmp))
            self.assertIsInstance(result, Path)

    def test_directory_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = queue._state_dir(Path(tmp))
            self.assertTrue(result.is_dir())

    def test_path_ends_with_expected_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = queue._state_dir(Path(tmp))
            self.assertTrue(str(result).endswith("workspace/local_exec/state"))


# ---------------------------------------------------------------------------
# ledger_path
# ---------------------------------------------------------------------------

class TestLedgerPath(unittest.TestCase):
    """Tests for ledger_path() — returns jobs.jsonl path."""

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = queue.ledger_path(Path(tmp))
            self.assertIsInstance(result, Path)

    def test_filename_is_jobs_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = queue.ledger_path(Path(tmp))
            self.assertEqual(result.name, "jobs.jsonl")


# ---------------------------------------------------------------------------
# lock_path
# ---------------------------------------------------------------------------

class TestLockPath(unittest.TestCase):
    """Tests for lock_path() — returns jobs.lock path."""

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = queue.lock_path(Path(tmp))
            self.assertIsInstance(result, Path)

    def test_filename_is_jobs_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = queue.lock_path(Path(tmp))
            self.assertEqual(result.name, "jobs.lock")


# ---------------------------------------------------------------------------
# _append_event
# ---------------------------------------------------------------------------

class TestAppendEvent(unittest.TestCase):
    """Tests for _append_event() — appends JSON line to ledger."""

    def test_creates_ledger_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue._append_event(Path(tmp), {"type": "test"})
            ledger = queue.ledger_path(Path(tmp))
            self.assertTrue(ledger.exists())

    def test_written_json_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue._append_event(Path(tmp), {"x": 42})
            ledger = queue.ledger_path(Path(tmp))
            line = ledger.read_text(encoding="utf-8").strip()
            obj = json.loads(line)
            self.assertEqual(obj["x"], 42)

    def test_multiple_appends(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue._append_event(Path(tmp), {"n": 1})
            queue._append_event(Path(tmp), {"n": 2})
            ledger = queue.ledger_path(Path(tmp))
            lines = [l for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
