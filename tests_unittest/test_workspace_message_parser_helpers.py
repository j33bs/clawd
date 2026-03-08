"""Tests for pure helpers in workspace/message_parser.py (root-level variant).

Pure stdlib (re only) — no stubs needed.
Note: this is the simpler variant without 'numbers', 'length', or
should_auto_respond; covered separately from workspace/memory/message_parser.py.

Covers:
- MessageParser.__init__
- MessageParser.parse (raw, intents, entities, sentiment)
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PARSER_PATH = REPO_ROOT / "workspace" / "message_parser.py"

_spec = _ilu.spec_from_file_location("workspace_message_parser_real", str(PARSER_PATH))
wmp = _ilu.module_from_spec(_spec)
sys.modules["workspace_message_parser_real"] = wmp
_spec.loader.exec_module(wmp)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestWMPInit(unittest.TestCase):
    """Tests for MessageParser.__init__ — intent_patterns structure."""

    def test_has_intent_patterns(self):
        parser = wmp.MessageParser()
        self.assertTrue(hasattr(parser, "intent_patterns"))

    def test_intent_patterns_is_dict(self):
        self.assertIsInstance(wmp.MessageParser().intent_patterns, dict)

    def test_expected_intents_present(self):
        p = wmp.MessageParser()
        for intent in ("research", "code", "question", "command", "status", "relationship"):
            self.assertIn(intent, p.intent_patterns)


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

class TestWMPParse(unittest.TestCase):
    """Tests for MessageParser.parse() — root-level variant."""

    def setUp(self):
        self.parser = wmp.MessageParser()

    def test_returns_dict(self):
        result = self.parser.parse("hello")
        self.assertIsInstance(result, dict)

    def test_has_raw_key(self):
        self.assertIn("raw", self.parser.parse("hello"))

    def test_has_intents_key(self):
        self.assertIn("intents", self.parser.parse("hello"))

    def test_has_entities_key(self):
        self.assertIn("entities", self.parser.parse("hello"))

    def test_has_sentiment_key(self):
        self.assertIn("sentiment", self.parser.parse("hello"))

    def test_no_length_key(self):
        # root variant does not emit 'length'
        result = self.parser.parse("hello")
        self.assertNotIn("length", result)

    def test_raw_lowercased(self):
        result = self.parser.parse("HELLO WORLD")
        self.assertEqual(result["raw"], "hello world")

    def test_entities_has_urls_and_paths(self):
        result = self.parser.parse("hello")
        self.assertIn("urls", result["entities"])
        self.assertIn("paths", result["entities"])

    def test_entities_no_numbers_key(self):
        # root variant omits 'numbers'
        result = self.parser.parse("42 items")
        self.assertNotIn("numbers", result["entities"])

    def test_extracts_url(self):
        result = self.parser.parse("see https://example.com for details")
        self.assertIn("https://example.com", result["entities"]["urls"])

    def test_neutral_sentiment(self):
        result = self.parser.parse("xyz blorp narf")
        self.assertAlmostEqual(result["sentiment"], 0.5)

    def test_positive_sentiment(self):
        result = self.parser.parse("great work, thanks!")
        self.assertGreater(result["sentiment"], 0.5)

    def test_negative_sentiment(self):
        result = self.parser.parse("bad result, stop now")
        self.assertLess(result["sentiment"], 0.5)

    def test_detects_research_intent(self):
        result = self.parser.parse("please research this topic")
        self.assertIn("research", result["intents"])

    def test_detects_code_intent(self):
        result = self.parser.parse("write a function")
        self.assertIn("code", result["intents"])

    def test_detects_question_intent(self):
        result = self.parser.parse("what is this?")
        self.assertIn("question", result["intents"])

    def test_empty_intents_for_garbage(self):
        result = self.parser.parse("xyzzy blorp")
        self.assertEqual(result["intents"], [])


if __name__ == "__main__":
    unittest.main()
