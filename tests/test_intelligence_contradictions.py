import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.intelligence.contradictions import detect_contradictions
from hivemind.models import KnowledgeUnit
from hivemind.store import HiveMindStore


class TestContradictions(unittest.TestCase):
    def test_fact_collision_and_decision_reversal(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "hivemind"
            store = HiveMindStore(base)
            review_path = base / "review_queue.json"

            store.put(KnowledgeUnit(kind="fact", source="same_source", agent_scope="shared"), "Ollama host is localhost")
            store.put(KnowledgeUnit(kind="fact", source="same_source", agent_scope="shared"), "Ollama host is not localhost")
            store.put(
                KnowledgeUnit(kind="decision", source="test", agent_scope="shared", metadata={"tag": "ollama_host"}),
                "Use localhost for Ollama",
            )
            store.put(
                KnowledgeUnit(kind="decision", source="test", agent_scope="shared", metadata={"tag": "ollama_host"}),
                "Do not use localhost for Ollama",
            )

            reports = detect_contradictions(store.all_units(), review_queue_path=review_path)
            reasons = "\n".join(r["reason"] for r in reports)
            self.assertIn("Fact collision", reasons)
            self.assertIn("Decision reversal", reasons)
            self.assertTrue(review_path.exists())


if __name__ == "__main__":
    unittest.main()
