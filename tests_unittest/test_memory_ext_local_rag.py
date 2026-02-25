import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from memory_ext.local_rag import LocalVectorDB, SemanticSearch, rag_answer


class TestMemoryExtLocalRag(unittest.TestCase):
    def test_search_and_answer(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            index = root / "workspace" / "state_runtime" / "memory_ext" / "rag_index.jsonl"
            manifest = root / "workspace" / "state_runtime" / "memory_ext" / "rag_docs_manifest.jsonl"
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                db = LocalVectorDB(index_path=index, manifest_path=manifest)
                db.add({"id": "a", "text": "TACTI framework integration memo", "source": "fixture"})
                db.add({"id": "b", "text": "garden notes and weather", "source": "fixture"})
                results = SemanticSearch("TACTI framework", top_k=1, db=db)
                self.assertEqual(results[0]["id"], "a")
                answer = rag_answer("TACTI framework", context_limit=1, db=db)
                self.assertIn("TACTI", answer["answer"])
                self.assertEqual(answer["sources"][0]["id"], "a")

    def test_off_by_default_add_is_noop(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "rag_index.jsonl"
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                db = LocalVectorDB(index_path=index)
                out = db.add({"text": "x"})
                self.assertIsNone(out)
                self.assertFalse(index.exists())


if __name__ == "__main__":
    unittest.main()
