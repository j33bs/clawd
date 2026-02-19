import json
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


class TestRedactionIngest(unittest.TestCase):
    def test_redaction_happens_before_store(self):
        with tempfile.TemporaryDirectory() as td:
            store = HiveMindStore(Path(td) / "hivemind")
            original = "api_key=plainsecretvalue token=abc1234567890"
            store.put(KnowledgeUnit(kind="fact", source="test", agent_scope="main"), original)

            lines = store.units_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            row = json.loads(lines[0])
            self.assertNotIn("plainsecretvalue", row["content"])
            self.assertIn("[REDACTED]", row["content"])


if __name__ == "__main__":
    unittest.main()
