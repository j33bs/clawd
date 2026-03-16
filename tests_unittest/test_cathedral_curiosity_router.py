import json
import tempfile
import unittest
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.curiosity_router import CuriosityRouter
from cathedral.novelty_archive import NoveltyArchive


class _NoSpawnCuriosityRouter(CuriosityRouter):
    def _spawn_research_wanderer(self, topic: str) -> str:
        del topic
        return "ok:test"


class TestCuriosityRouter(unittest.TestCase):
    def test_triggered_route_returns_3_to_5_leads(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            telemetry_path = tmp / "system_physiology.json"
            telemetry_path.write_text(
                json.dumps(
                    {
                        "cpu_temp": 68,
                        "gpu_vram": 0.62,
                        "fan_gpu": 1800,
                        "disk_io": 0.21,
                    }
                ),
                encoding="utf-8",
            )

            archive = NoveltyArchive(archive_dir=tmp / "novelty", similarity_threshold=0.95)
            router = _NoSpawnCuriosityRouter(
                output_path=tmp / "curiosity_latest.json",
                telemetry_path=telemetry_path,
                archive=archive,
            )

            out = router.route(
                query="why did retrieval return no semantic match",
                response_text="",
                confidence=0.1,
                semantic_match=False,
                reason_code="response_null",
            )

            self.assertTrue(out.get("triggered"), out)
            self.assertGreaterEqual(len(out.get("leads", [])), 3)
            self.assertLessEqual(len(out.get("leads", [])), 5)
            self.assertTrue(out.get("seed"))


if __name__ == "__main__":
    unittest.main()
