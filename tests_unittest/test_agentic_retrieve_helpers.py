"""Tests for workspace/knowledge_base/agentic/retrieve.py pure helper functions.

Covers (no subprocess, no vector store):
- _resolve_retrieval_mode
- _vector_context_to_result
"""
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_DIR = REPO_ROOT / "workspace" / "knowledge_base"

# Stub out the imports that require running processes / embeddings.
# Must set up the `agentic` package with __path__ before inserting KB_DIR.
_agentic_pkg = types.ModuleType("agentic")
_agentic_pkg.__path__ = [str(KB_DIR / "agentic")]
sys.modules.setdefault("agentic", _agentic_pkg)

_intent_mod = types.ModuleType("agentic.intent")
_intent_mod.build_search_query = lambda q: q
_intent_mod.extract_entities_from_query = lambda q: []
sys.modules.setdefault("agentic.intent", _intent_mod)

_retrieval_mod = types.ModuleType("retrieval")
_retrieval_mod.retrieve = lambda *a, **kw: {"contexts": [], "mode": "HYBRID", "authoritative": True}
sys.modules.setdefault("retrieval", _retrieval_mod)

if str(KB_DIR) not in sys.path:
    sys.path.insert(0, str(KB_DIR))

import importlib as _il
rt = _il.import_module("agentic.retrieve")


# ---------------------------------------------------------------------------
# _resolve_retrieval_mode
# ---------------------------------------------------------------------------

class TestResolveRetrievalMode(unittest.TestCase):
    """Tests for _resolve_retrieval_mode() — intent+query → PRECISE/FAST/HYBRID."""

    def test_governance_strategy_is_precise(self):
        result = rt._resolve_retrieval_mode("any query", {"strategy": "governance"})
        self.assertEqual(result, "PRECISE")

    def test_research_strategy_is_precise(self):
        result = rt._resolve_retrieval_mode("any query", {"strategy": "research"})
        self.assertEqual(result, "PRECISE")

    def test_code_critical_strategy_is_precise(self):
        result = rt._resolve_retrieval_mode("any query", {"strategy": "code_critical"})
        self.assertEqual(result, "PRECISE")

    def test_search_autocomplete_strategy_is_fast(self):
        result = rt._resolve_retrieval_mode("any query", {"strategy": "search_autocomplete"})
        self.assertEqual(result, "FAST")

    def test_governance_in_query_text_is_precise(self):
        result = rt._resolve_retrieval_mode("governance decision history", {})
        self.assertEqual(result, "PRECISE")

    def test_research_in_query_text_is_precise(self):
        result = rt._resolve_retrieval_mode("research findings on X", {})
        self.assertEqual(result, "PRECISE")

    def test_generic_query_is_hybrid(self):
        result = rt._resolve_retrieval_mode("what is the weather today?", {})
        self.assertEqual(result, "HYBRID")

    def test_returns_string(self):
        self.assertIsInstance(rt._resolve_retrieval_mode("q", {}), str)


# ---------------------------------------------------------------------------
# _vector_context_to_result
# ---------------------------------------------------------------------------

class TestVectorContextToResult(unittest.TestCase):
    """Tests for _vector_context_to_result() — context dict → standardised result row."""

    def _ctx(self, **overrides):
        base = {
            "path": "docs/guide.md",
            "doc_id": "docs/guide.md",
            "chunk_id": "s0001-c0001",
            "text": "Hello world content here",
            "score": 0.85,
            "model_id": "all-MiniLM-L6-v2",
            "section": "Intro",
        }
        base.update(overrides)
        return base

    def test_returns_dict(self):
        result = rt._vector_context_to_result(self._ctx(), "HYBRID", True)
        self.assertIsInstance(result, dict)

    def test_source_is_kb_vectors(self):
        result = rt._vector_context_to_result(self._ctx(), "HYBRID", True)
        self.assertEqual(result["source"], "kb_vectors")

    def test_path_preserved(self):
        result = rt._vector_context_to_result(self._ctx(path="a/b.md"), "HYBRID", True)
        self.assertEqual(result["path"], "a/b.md")

    def test_score_preserved(self):
        result = rt._vector_context_to_result(self._ctx(score=0.77), "HYBRID", True)
        self.assertAlmostEqual(result["score"], 0.77)

    def test_retrieval_mode_preserved(self):
        result = rt._vector_context_to_result(self._ctx(), "PRECISE", True)
        self.assertEqual(result["retrieval_mode"], "PRECISE")

    def test_authoritative_flag_preserved(self):
        result = rt._vector_context_to_result(self._ctx(), "HYBRID", False)
        self.assertFalse(result["authoritative"])

    def test_content_truncated_at_1200(self):
        result = rt._vector_context_to_result(self._ctx(text="x" * 2000), "HYBRID", True)
        self.assertLessEqual(len(result["content"]), 1200)

    def test_missing_score_defaults_to_0(self):
        result = rt._vector_context_to_result({"text": "hello"}, "HYBRID", True)
        self.assertEqual(result["score"], 0.0)


if __name__ == "__main__":
    unittest.main()
