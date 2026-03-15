import unittest
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from store import mirror_readers


class TestMirrorReadersCathedralSnapshot(unittest.TestCase):
    def test_collect_snapshot_includes_active_renderer_and_cathedral_feed(self):
        cathedral_state = {
            "status": "OK",
            "system_physiology": {"ts": "2026-03-06T01:02:03Z"},
            "tacti_state": {"ts": "2026-03-06T01:02:04Z"},
            "fishtank_state": {"ts": "2026-03-06T01:02:05Z"},
            "curiosity": {"ts": "2026-03-06T01:02:06Z"},
            "error": "",
        }

        with mock.patch.object(mirror_readers, "_git_short_sha", return_value="abc1234"), mock.patch.object(
            mirror_readers, "read_linear_tail", return_value={"status": "OK"}
        ), mock.patch.object(mirror_readers, "read_phi_metrics", return_value={"status": "OK"}), mock.patch.object(
            mirror_readers, "read_inquiry_momentum", return_value={"status": "OK"}
        ), mock.patch.object(mirror_readers, "read_heartbeat", return_value={"status": "OK"}), mock.patch.object(
            mirror_readers, "read_ticker", return_value={"status": "OK"}
        ), mock.patch.object(mirror_readers, "read_vllm_coder", return_value={"status": "OK"}), mock.patch.object(
            mirror_readers, "read_cathedral_state", return_value=cathedral_state
        ):
            snapshot = mirror_readers.collect_snapshot()

        self.assertEqual(snapshot.get("active_renderer_name"), "cathedral_fishtank")
        self.assertEqual(snapshot.get("active_renderer_version"), "abc1234")
        self.assertIn("cathedral_state", snapshot.get("feeds", {}))
        self.assertEqual(snapshot.get("last_update", {}).get("system_physiology"), "2026-03-06T01:02:03Z")
        self.assertEqual(snapshot.get("last_update", {}).get("tacti_state"), "2026-03-06T01:02:04Z")
        self.assertEqual(snapshot.get("last_update", {}).get("fishtank_state"), "2026-03-06T01:02:05Z")
        self.assertEqual(snapshot.get("last_update", {}).get("curiosity_state"), "2026-03-06T01:02:06Z")


if __name__ == "__main__":
    unittest.main()
