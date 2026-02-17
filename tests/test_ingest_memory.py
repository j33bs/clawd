import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.ingest.memory_md import ingest_memory_md, parse_memory_chunks
from hivemind.store import HiveMindStore


class TestIngestMemory(unittest.TestCase):
    def test_chunking_dedup_and_hash_stability(self):
        text = """## Lessons Learned
- Keep tests deterministic
- Redact before embedding

### Facts
The system is local-first.
"""
        chunks = parse_memory_chunks(text)
        self.assertGreaterEqual(len(chunks), 2)

        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "hivemind"
            store = HiveMindStore(base)
            memory_path = Path(td) / "MEMORY.md"
            memory_path.write_text(text, encoding="utf-8")

            first = ingest_memory_md(memory_path=memory_path, store=store)
            self.assertGreater(first["stored"], 0)

            second = ingest_memory_md(memory_path=memory_path, store=store)
            self.assertEqual(second["stored"], 0)
            self.assertEqual(second["skipped"], second["processed"])

            h1 = store.content_hash("alpha\n")
            h2 = store.content_hash("alpha  \n")
            self.assertEqual(h1, h2)


if __name__ == "__main__":
    unittest.main()
