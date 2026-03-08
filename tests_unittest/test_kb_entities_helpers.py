"""Tests for workspace/knowledge_base/graph/entities.py pure helper functions.

Covers (no I/O, no network):
- extract_entities
- extract_decision_markers
- extract_lesson_markers
- classify_knowledge_type
- extract_relationships
- extract_key_phrases
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTITIES_DIR = REPO_ROOT / "workspace" / "knowledge_base" / "graph"
if str(ENTITIES_DIR) not in sys.path:
    sys.path.insert(0, str(ENTITIES_DIR))

from entities import (  # noqa: E402
    classify_knowledge_type,
    extract_decision_markers,
    extract_entities,
    extract_key_phrases,
    extract_lesson_markers,
    extract_relationships,
)


# ---------------------------------------------------------------------------
# extract_entities
# ---------------------------------------------------------------------------

class TestExtractEntities(unittest.TestCase):
    """Tests for extract_entities() — keyword-based entity extraction."""

    def test_detects_system_openclaw(self):
        result = extract_entities("OpenClaw is the orchestrator")
        self.assertIn("system:openclaw", result)

    def test_detects_model_claude(self):
        result = extract_entities("using Claude for generation")
        self.assertIn("model:claude", result)

    def test_detects_term_routing(self):
        result = extract_entities("routing logic for requests")
        self.assertIn("term:routing", result)

    def test_detects_term_memory(self):
        result = extract_entities("memory subsystem activated")
        self.assertIn("term:memory", result)

    def test_empty_text_returns_list(self):
        result = extract_entities("")
        self.assertIsInstance(result, list)

    def test_no_entities_returns_empty(self):
        result = extract_entities("the quick brown fox jumps")
        self.assertEqual(result, [])

    def test_returns_list(self):
        self.assertIsInstance(extract_entities("Claude"), list)

    def test_no_duplicates(self):
        result = extract_entities("claude claude claude")
        self.assertEqual(len([e for e in result if e == "model:claude"]), 1)


# ---------------------------------------------------------------------------
# extract_decision_markers
# ---------------------------------------------------------------------------

class TestExtractDecisionMarkers(unittest.TestCase):
    """Tests for extract_decision_markers() — bool marker detection."""

    def test_decided_detected(self):
        self.assertTrue(extract_decision_markers("we decided to use it"))

    def test_will_use_detected(self):
        self.assertTrue(extract_decision_markers("we will use Redis here"))

    def test_approved_detected(self):
        self.assertTrue(extract_decision_markers("jeebs approved the plan"))

    def test_no_marker_returns_false(self):
        self.assertFalse(extract_decision_markers("the system is running fine"))

    def test_empty_returns_false(self):
        self.assertFalse(extract_decision_markers(""))

    def test_returns_bool(self):
        self.assertIsInstance(extract_decision_markers("decided"), bool)


# ---------------------------------------------------------------------------
# extract_lesson_markers
# ---------------------------------------------------------------------------

class TestExtractLessonMarkers(unittest.TestCase):
    """Tests for extract_lesson_markers() — bool lesson detection."""

    def test_learned_detected(self):
        self.assertTrue(extract_lesson_markers("we learned this the hard way"))

    def test_bug_detected(self):
        self.assertTrue(extract_lesson_markers("found a bug in the parser"))

    def test_mistake_detected(self):
        self.assertTrue(extract_lesson_markers("that was a mistake"))

    def test_insight_detected(self):
        self.assertTrue(extract_lesson_markers("key insight from the experiment"))

    def test_no_marker_returns_false(self):
        self.assertFalse(extract_lesson_markers("everything works as expected"))

    def test_empty_returns_false(self):
        self.assertFalse(extract_lesson_markers(""))

    def test_returns_bool(self):
        self.assertIsInstance(extract_lesson_markers("learned"), bool)


# ---------------------------------------------------------------------------
# classify_knowledge_type
# ---------------------------------------------------------------------------

class TestClassifyKnowledgeType(unittest.TestCase):
    """Tests for classify_knowledge_type() — text → type string."""

    def test_decision_wins_over_lesson(self):
        text = "we decided and also learned"
        result = classify_knowledge_type(text)
        self.assertEqual(result, "decision")

    def test_lesson_when_no_decision(self):
        self.assertEqual(classify_knowledge_type("we learned this insight"), "lesson")

    def test_procedure_from_heading(self):
        self.assertEqual(classify_knowledge_type("## Step one\ndo something"), "procedure")

    def test_fact_fallback(self):
        self.assertEqual(classify_knowledge_type("the sky is blue"), "fact")

    def test_returns_string(self):
        self.assertIsInstance(classify_knowledge_type("text"), str)


# ---------------------------------------------------------------------------
# extract_relationships
# ---------------------------------------------------------------------------

class TestExtractRelationships(unittest.TestCase):
    """Tests for extract_relationships() — dependency detection."""

    def test_depends_on_creates_relation(self):
        entities = ["system:openclaw", "model:claude"]
        result = extract_relationships("A depends on B", entities)
        self.assertTrue(len(result) > 0)
        types = {r["type"] for r in result}
        self.assertIn("depends_on", types)

    def test_no_relation_keyword_empty(self):
        result = extract_relationships("nothing here", ["system:openclaw"])
        self.assertEqual(result, [])

    def test_returns_list(self):
        self.assertIsInstance(extract_relationships("depends on", []), list)

    def test_related_to_keyword(self):
        entities = ["model:gpt", "term:routing"]
        result = extract_relationships("A is related to B", entities)
        types = {r["type"] for r in result}
        self.assertIn("related_to", types)

    def test_relation_has_from_to_type_keys(self):
        entities = ["model:gpt", "model:claude"]
        result = extract_relationships("A caused by B", entities)
        if result:
            self.assertIn("from", result[0])
            self.assertIn("to", result[0])
            self.assertIn("type", result[0])


# ---------------------------------------------------------------------------
# extract_key_phrases
# ---------------------------------------------------------------------------

class TestExtractKeyPhrases(unittest.TestCase):
    """Tests for extract_key_phrases() — phrase extraction."""

    def test_returns_list(self):
        self.assertIsInstance(extract_key_phrases("Hello World routing"), list)

    def test_respects_max_phrases(self):
        result = extract_key_phrases("routing memory model config fallback agent system", max_phrases=3)
        self.assertLessEqual(len(result), 3)

    def test_important_terms_included(self):
        result = extract_key_phrases("routing and memory for agents")
        terms = set(result)
        self.assertTrue(terms & {"routing", "memory", "agent"})

    def test_empty_returns_empty(self):
        result = extract_key_phrases("")
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
