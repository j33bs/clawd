import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = REPO_ROOT / "workspace"
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

import oracle_priority as _op  # noqa: E402


class OraclePriorityTests(unittest.TestCase):
    def test_acquire_and_release_lease(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "oracle_priority.json"
            with mock.patch.object(_op, "ORACLE_PRIORITY_STATE_PATH", state_path):
                lease = _op.acquire_lease("oracle-a", purpose="source_ui_oracle", max_wait_seconds=0.1)
                self.assertIsNotNone(lease)
                active = _op.get_active_lease()
                self.assertIsNotNone(active)
                self.assertEqual(active["owner"], "oracle-a")
                self.assertTrue(_op.release_lease("oracle-a"))
                self.assertIsNone(_op.get_active_lease())

    def test_wait_for_clear_returns_cleared_after_release(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "oracle_priority.json"
            with mock.patch.object(_op, "ORACLE_PRIORITY_STATE_PATH", state_path):
                lease = _op.acquire_lease("oracle-a", max_wait_seconds=0.1)
                self.assertIsNotNone(lease)
                self.assertTrue(_op.release_lease("oracle-a"))
                result = _op.wait_for_clear(max_wait_seconds=0.2, poll_interval=0.01)
                self.assertTrue(result["cleared"])

    def test_expired_lease_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "oracle_priority.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                '{"owner":"oracle-old","purpose":"source_ui_oracle","acquired_at":1.0,"expires_at":1.5,"metadata":{}}',
                encoding="utf-8",
            )
            with mock.patch.object(_op, "ORACLE_PRIORITY_STATE_PATH", state_path):
                self.assertIsNone(_op.get_active_lease(now=5.0))

