import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.intelligence import summaries
from hivemind.models import KnowledgeUnit
from hivemind.store import HiveMindStore


class TestSummaries(unittest.TestCase):
    def test_cross_agent_digest_generation(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "hivemind"
            store = HiveMindStore(base)

            store.put(KnowledgeUnit(kind="decision", source="x", agent_scope="shared"), "Use 127.0.0.1 for Ollama")
            store.put(KnowledgeUnit(kind="lesson", source="x", agent_scope="shared"), "Always redact before embedding")
            store.put(KnowledgeUnit(kind="code_snippet", source="x", agent_scope="shared", metadata={"file": "a.py"}), "print('ok')")

            summaries.REPO_ROOT = Path(td)
            summaries.DIGEST_DIR = base / "digests"
            result = summaries.generate_cross_agent_summary("7d", store=store)

            self.assertTrue(Path(result["path"]).exists())
            self.assertIn("HiveMind Digest", result["markdown"])
            self.assertGreaterEqual(result["counts"]["shared"], 3)


if __name__ == "__main__":
    unittest.main()
