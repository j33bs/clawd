"""Tests for pure helpers in workspace/knowledge_base/graph/entities.py.

Purely stdlib (re, typing) — no stubs needed.

Covers:
- extract_entities
- extract_decision_markers
- extract_lesson_markers
- classify_knowledge_type
- extract_relationships
- extract_key_phrases
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTITIES_PATH = REPO_ROOT / "workspace" / "knowledge_base" / "graph" / "entities.py"

_spec = _ilu.spec_from_file_location("kb_graph_entities_real", str(ENTITIES_PATH))
ent = _ilu.module_from_spec(_spec)
sys.modules["kb_graph_entities_real"] = ent
_spec.loader.exec_module(ent)


# ---------------------------------------------------------------------------
# extract_entities
# ---------------------------------------------------------------------------

class TestExtractEntities(unittest.TestCase):
    """Tests for extract_entities() — keyword-based entity extraction."""

    def test_returns_list(self):
        result = ent.extract_entities("Claude is an AI model")
        self.assertIsInstance(result, list)

    def test_extracts_model_entity(self):
        result = ent.extract_entities("We use claude for our routing tests.")
        self.assertIn("model:claude", result)

    def test_extracts_system_entity(self):
        result = ent.extract_entities("openclaw manages the routing")
        self.assertIn("system:openclaw", result)

    def test_extracts_provider_entity(self):
        result = ent.extract_entities("We call anthropic for completions.")
        self.assertIn("provider:anthropic", result)

    def test_extracts_technical_term(self):
        result = ent.extract_entities("Uses embedding vector for retrieval.")
        self.assertTrue(any("term:" in e for e in result))

    def test_empty_text_returns_empty(self):
        result = ent.extract_entities("")
        self.assertEqual(result, [])

    def test_no_duplicates(self):
        result = ent.extract_entities("claude claude claude")
        self.assertEqual(len(result), result.count("model:claude"))


# ---------------------------------------------------------------------------
# extract_decision_markers
# ---------------------------------------------------------------------------

class TestExtractDecisionMarkers(unittest.TestCase):
    """Tests for extract_decision_markers() — bool check for decision words."""

    def test_decided_returns_true(self):
        self.assertTrue(ent.extract_decision_markers("We decided to use OpenAI."))

    def test_confirmed_returns_true(self):
        self.assertTrue(ent.extract_decision_markers("jeebs confirmed the approach."))

    def test_plain_text_returns_false(self):
        self.assertFalse(ent.extract_decision_markers("The model processed the input."))

    def test_returns_bool(self):
        result = ent.extract_decision_markers("test")
        self.assertIsInstance(result, bool)

    def test_empty_returns_false(self):
        self.assertFalse(ent.extract_decision_markers(""))


# ---------------------------------------------------------------------------
# extract_lesson_markers
# ---------------------------------------------------------------------------

class TestExtractLessonMarkers(unittest.TestCase):
    """Tests for extract_lesson_markers() — bool check for lesson words."""

    def test_learned_returns_true(self):
        self.assertTrue(ent.extract_lesson_markers("We learned that caching helps."))

    def test_bug_returns_true(self):
        self.assertTrue(ent.extract_lesson_markers("Fixed a bug in the router."))

    def test_plain_text_returns_false(self):
        self.assertFalse(ent.extract_lesson_markers("The system is running fine."))

    def test_returns_bool(self):
        self.assertIsInstance(ent.extract_lesson_markers("test"), bool)


# ---------------------------------------------------------------------------
# classify_knowledge_type
# ---------------------------------------------------------------------------

class TestClassifyKnowledgeType(unittest.TestCase):
    """Tests for classify_knowledge_type() — returns one of four types."""

    def test_decision_text(self):
        result = ent.classify_knowledge_type("We decided to use the new model.")
        self.assertEqual(result, "decision")

    def test_lesson_text(self):
        result = ent.classify_knowledge_type("We learned about embedding drift.")
        self.assertEqual(result, "lesson")

    def test_markdown_heading_is_procedure(self):
        result = ent.classify_knowledge_type("## Setup Instructions\nDo this.")
        self.assertEqual(result, "procedure")

    def test_plain_text_is_fact(self):
        result = ent.classify_knowledge_type("The server is running on port 8080.")
        self.assertEqual(result, "fact")

    def test_returns_string(self):
        self.assertIsInstance(ent.classify_knowledge_type("hello"), str)


# ---------------------------------------------------------------------------
# extract_relationships
# ---------------------------------------------------------------------------

class TestExtractRelationships(unittest.TestCase):
    """Tests for extract_relationships() — pattern-based relationship extraction."""

    def test_depends_on_pattern(self):
        entities = ["model:claude", "system:openclaw"]
        result = ent.extract_relationships("A depends on B", entities)
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

    def test_no_pattern_returns_empty(self):
        entities = ["model:claude"]
        result = ent.extract_relationships("Claude is very capable.", entities)
        self.assertEqual(result, [])

    def test_related_to_pattern(self):
        entities = ["system:openclaw", "model:gemini"]
        result = ent.extract_relationships("OpenClaw is related to Gemini", entities)
        self.assertTrue(len(result) > 0)

    def test_returns_list(self):
        result = ent.extract_relationships("test", [])
        self.assertIsInstance(result, list)


# ---------------------------------------------------------------------------
# extract_key_phrases
# ---------------------------------------------------------------------------

class TestExtractKeyPhrases(unittest.TestCase):
    """Tests for extract_key_phrases() — returns up to max_phrases phrases."""

    def test_returns_list(self):
        result = ent.extract_key_phrases("Claude uses routing and memory.")
        self.assertIsInstance(result, list)

    def test_max_phrases_respected(self):
        result = ent.extract_key_phrases("many words here routing memory model config fallback", max_phrases=3)
        self.assertLessEqual(len(result), 3)

    def test_important_terms_extracted(self):
        result = ent.extract_key_phrases("uses routing and memory for the agent")
        self.assertTrue(any("routing" in p or "memory" in p or "agent" in p for p in result))

    def test_empty_string(self):
        result = ent.extract_key_phrases("")
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
