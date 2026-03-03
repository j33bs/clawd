import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_ROOT = REPO_ROOT / "workspace" / "knowledge_base"
if str(KB_ROOT) not in sys.path:
    sys.path.insert(0, str(KB_ROOT))

from indexer import run_index
from retrieval import retrieve
from vector_store_lancedb import LanceVectorStore, MINILM_TABLE, MODERNBERT_TABLE


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_tiny_corpus(root: Path):
    _write(
        root / "workspace" / "knowledge_base" / "data" / "tiny_doc.md",
        "# ModernBERT Canonical\n\nModernBERT is the authoritative retrieval model for synthesis grounding.",
    )
    _write(root / "MEMORY.md", "MiniLM is accelerator-only for candidate generation.\n")
    _write(root / "memory" / "2026-03-03.md", "Hybrid retrieval reranks with ModernBERT.\n")
    _write(
        root / "workspace" / "governance" / "OPEN_QUESTIONS.md",
        "Governance asks for fail-closed behavior when canonical index is unavailable.\n",
    )


class TestEmbeddingsContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        _build_tiny_corpus(cls.root)
        cls.db_dir = cls.root / "workspace" / "knowledge_base" / "data" / "vectors.lance"
        cls.meta_path = cls.root / "workspace" / "knowledge_base" / "data" / "embeddings.meta.json"
        cls.evidence_dir = cls.root / "evidence"
        cls.env = {
            "OPENCLAW_KB_REPO_ROOT": str(cls.root),
            "OPENCLAW_KB_VECTOR_DB_DIR": str(cls.db_dir),
            "OPENCLAW_KB_EMBED_META_PATH": str(cls.meta_path),
            "OPENCLAW_KB_EMBEDDINGS_BACKEND": "mock",
        }
        with patch.dict(os.environ, cls.env, clear=False):
            cls.index_summary = run_index(evidence_dir=str(cls.evidence_dir))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_indexing_creates_both_tables(self):
        with patch.dict(os.environ, self.env, clear=False):
            store = LanceVectorStore(str(self.db_dir))
            modern = store.stats(MODERNBERT_TABLE)
            minilm = store.stats(MINILM_TABLE)

        self.assertTrue(modern["exists"])
        self.assertTrue(minilm["exists"])
        self.assertGreater(modern["rows"], 0)
        self.assertGreater(minilm["rows"], 0)

    def test_hybrid_is_authoritative_with_contexts(self):
        with patch.dict(os.environ, self.env, clear=False):
            payload = retrieve("authoritative retrieval model", mode="HYBRID", k=4)

        self.assertTrue(payload["authoritative"])
        self.assertEqual(payload["mode"], "HYBRID")
        self.assertGreater(len(payload["contexts"]), 0)

    def test_precise_fails_closed_when_modernbert_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env = {
                "OPENCLAW_KB_REPO_ROOT": str(root),
                "OPENCLAW_KB_VECTOR_DB_DIR": str(root / "workspace" / "knowledge_base" / "data" / "vectors.lance"),
                "OPENCLAW_KB_EMBED_META_PATH": str(root / "workspace" / "knowledge_base" / "data" / "embeddings.meta.json"),
                "OPENCLAW_KB_EMBEDDINGS_BACKEND": "mock",
            }
            with patch.dict(os.environ, env, clear=False):
                with self.assertRaises(RuntimeError):
                    retrieve("fail closed", mode="PRECISE", k=3)

    def test_fast_is_non_authoritative(self):
        with patch.dict(os.environ, self.env, clear=False):
            payload = retrieve("candidate generation", mode="FAST", k=4)

        self.assertFalse(payload["authoritative"])
        self.assertFalse(payload["synthesis_safe"])
        self.assertIn("candidate-only", " ".join(payload.get("notes", [])))


if __name__ == "__main__":
    unittest.main()
