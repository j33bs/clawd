import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.models import KnowledgeUnit
from hivemind.store import HiveMindStore


class TestQueryScope(unittest.TestCase):
    def test_agent_scope_isolation(self):
        with tempfile.TemporaryDirectory() as td:
            store = HiveMindStore(Path(td) / "hivemind")

            store.put(KnowledgeUnit(kind="fact", source="test", agent_scope="shared"), "shared ffmpeg command")
            store.put(KnowledgeUnit(kind="fact", source="test", agent_scope="main"), "main private ffmpeg command")
            store.put(KnowledgeUnit(kind="fact", source="test", agent_scope="claude-code"), "claude private ffmpeg command")

            main_hits = store.search(agent_scope="main", query="ffmpeg", limit=10)
            claude_hits = store.search(agent_scope="claude-code", query="ffmpeg", limit=10)

            main_scopes = {h["agent_scope"] for h in main_hits}
            claude_scopes = {h["agent_scope"] for h in claude_hits}

            self.assertIn("shared", main_scopes)
            self.assertIn("main", main_scopes)
            self.assertNotIn("claude-code", main_scopes)

            self.assertIn("shared", claude_scopes)
            self.assertIn("claude-code", claude_scopes)
            self.assertNotIn("main", claude_scopes)


if __name__ == "__main__":
    unittest.main()
