import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.intelligence import suggestions
from hivemind.models import KnowledgeUnit
from hivemind.store import HiveMindStore


class TestSuggestions(unittest.TestCase):
    def test_rate_limit_and_scope(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "hivemind"
            store = HiveMindStore(base)
            suggestions.STATE_PATH = base / "suggestions_state.json"

            store.put(KnowledgeUnit(kind="fact", source="x", agent_scope="main"), "Ollama config uses 127.0.0.1")
            store.put(KnowledgeUnit(kind="fact", source="x", agent_scope="claude-code"), "private claude hint")

            # Inject query history for temporal trigger
            for _ in range(4):
                store.log_event("query", agent="main", query="Ollama config", limit=5)

            out1 = suggestions.generate_suggestions("Ollama config", "main", session_id="s1")
            self.assertLessEqual(len(out1), 3)
            # Immediate repeat should hit cooldown.
            out2 = suggestions.generate_suggestions("Ollama config", "main", session_id="s1")
            self.assertEqual(out2, [])


if __name__ == "__main__":
    unittest.main()
