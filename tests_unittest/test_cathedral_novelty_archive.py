import tempfile
import unittest
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.novelty_archive import NoveltyArchive


class TestNoveltyArchive(unittest.TestCase):
    def test_duplicate_detection_flags_similar_paths(self):
        with tempfile.TemporaryDirectory() as td:
            archive = NoveltyArchive(archive_dir=Path(td) / "novelty", similarity_threshold=0.7)

            first = archive.archive(
                curiosity_seed="seed-a",
                exploration_path=["expand", "sample"],
                result_text="test lead alpha beta gamma",
                result_novelty_score=0.7,
                telemetry_snapshot={"cpu_temp": 60},
                source_query="alpha beta",
            )
            second = archive.archive(
                curiosity_seed="seed-b",
                exploration_path=["expand", "sample"],
                result_text="test lead alpha beta gamma",
                result_novelty_score=0.4,
                telemetry_snapshot={"cpu_temp": 62},
                source_query="alpha beta",
            )

            self.assertTrue(first.archived)
            self.assertFalse(first.duplicate)
            self.assertTrue(second.duplicate)
            self.assertGreaterEqual(second.similarity, 0.7)


if __name__ == "__main__":
    unittest.main()
