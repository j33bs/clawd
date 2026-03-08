"""Tests for pure helpers in workspace/memory/message_parser.py.

Pure stdlib (re only) — no stubs needed.

Covers:
- MessageParser.__init__ (intent_patterns structure)
- MessageParser.parse (raw, intents, entities, sentiment, length)
- MessageParser.should_auto_respond
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PARSER_PATH = REPO_ROOT / "workspace" / "memory" / "message_parser.py"

_spec = _ilu.spec_from_file_location("memory_message_parser_real", str(PARSER_PATH))
mp = _ilu.module_from_spec(_spec)
sys.modules["memory_message_parser_real"] = mp
_spec.loader.exec_module(mp)


# ---------------------------------------------------------------------------
# __init__ / intent_patterns
# ---------------------------------------------------------------------------

class TestMessageParserInit(unittest.TestCase):
    """Tests for MessageParser.__init__ — intent_patterns structure."""

    def test_has_intent_patterns(self):
        parser = mp.MessageParser()
        self.assertTrue(hasattr(parser, "intent_patterns"))

    def test_intent_patterns_is_dict(self):
        parser = mp.MessageParser()
        self.assertIsInstance(parser.intent_patterns, dict)

    def test_has_research_intent(self):
        self.assertIn("research", mp.MessageParser().intent_patterns)

    def test_has_code_intent(self):
        self.assertIn("code", mp.MessageParser().intent_patterns)

    def test_has_question_intent(self):
        self.assertIn("question", mp.MessageParser().intent_patterns)

    def test_has_command_intent(self):
        self.assertIn("command", mp.MessageParser().intent_patterns)

    def test_has_status_intent(self):
        self.assertIn("status", mp.MessageParser().intent_patterns)

    def test_has_relationship_intent(self):
        self.assertIn("relationship", mp.MessageParser().intent_patterns)

    def test_patterns_are_lists(self):
        for key, val in mp.MessageParser().intent_patterns.items():
            self.assertIsInstance(val, list, msg=f"patterns[{key!r}] should be a list")


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

class TestMessageParserParse(unittest.TestCase):
    """Tests for MessageParser.parse()."""

    def setUp(self):
        self.parser = mp.MessageParser()

    def test_returns_dict(self):
        result = self.parser.parse("hello")
        self.assertIsInstance(result, dict)

    def test_has_required_keys(self):
        result = self.parser.parse("hello")
        for key in ("raw", "intents", "entities", "sentiment", "length"):
            self.assertIn(key, result)

    def test_raw_is_lowercased(self):
        result = self.parser.parse("HELLO WORLD")
        self.assertEqual(result["raw"], "hello world")

    def test_length_matches_lowercased(self):
        result = self.parser.parse("Hello")
        self.assertEqual(result["length"], len("hello"))

    def test_intents_is_list(self):
        result = self.parser.parse("hello")
        self.assertIsInstance(result["intents"], list)

    def test_entities_has_urls_paths_numbers(self):
        result = self.parser.parse("hello")
        for key in ("urls", "paths", "numbers"):
            self.assertIn(key, result["entities"])

    def test_extracts_url(self):
        result = self.parser.parse("visit https://example.com now")
        self.assertIn("https://example.com", result["entities"]["urls"])

    def test_extracts_numbers(self):
        result = self.parser.parse("I need 42 items")
        self.assertIn("42", result["entities"]["numbers"])

    def test_default_sentiment_neutral(self):
        result = self.parser.parse("neutral message xyz")
        self.assertAlmostEqual(result["sentiment"], 0.5)

    def test_positive_sentiment(self):
        result = self.parser.parse("great work, thanks!")
        self.assertGreater(result["sentiment"], 0.5)

    def test_negative_sentiment(self):
        result = self.parser.parse("bad result, stop now")
        self.assertLess(result["sentiment"], 0.5)

    def test_negative_overrides_positive(self):
        # both positive ("great") and negative ("bad") present — negative wins
        result = self.parser.parse("great bad")
        self.assertLess(result["sentiment"], 0.5)

    def test_detects_research_intent(self):
        result = self.parser.parse("please research this topic")
        self.assertIn("research", result["intents"])

    def test_detects_question_intent(self):
        result = self.parser.parse("what is consciousness?")
        self.assertIn("question", result["intents"])

    def test_detects_code_intent(self):
        result = self.parser.parse("write a function to parse JSON")
        self.assertIn("code", result["intents"])

    def test_detects_command_intent(self):
        result = self.parser.parse("run the integration test")
        self.assertIn("command", result["intents"])

    def test_detects_status_intent(self):
        result = self.parser.parse("status check please")
        self.assertIn("status", result["intents"])

    def test_detects_relationship_intent(self):
        result = self.parser.parse("how is our relationship?")
        self.assertIn("relationship", result["intents"])

    def test_multiple_intents_detected(self):
        result = self.parser.parse("research and find how this works?")
        # "research"/"find" → research; "how"/"?" → question
        self.assertIn("research", result["intents"])
        self.assertIn("question", result["intents"])

    def test_no_intents_for_garbage(self):
        result = self.parser.parse("xyzzy blorp narf")
        self.assertEqual(result["intents"], [])


# ---------------------------------------------------------------------------
# should_auto_respond
# ---------------------------------------------------------------------------

class TestShouldAutoRespond(unittest.TestCase):
    """Tests for MessageParser.should_auto_respond()."""

    def setUp(self):
        self.parser = mp.MessageParser()

    def test_returns_bool(self):
        parsed = self.parser.parse("hello")
        result = self.parser.should_auto_respond(parsed)
        self.assertIsInstance(result, bool)

    def test_status_with_positive_sentiment_true(self):
        # "how's" → status intent; "thanks" → sentiment=0.7 > 0.6
        parsed = self.parser.parse("how's the status, thanks!")
        result = self.parser.should_auto_respond(parsed)
        self.assertTrue(result)

    def test_no_status_intent_returns_false(self):
        # "thanks" alone — positive sentiment but no status intent
        parsed = self.parser.parse("thanks a lot!")
        result = self.parser.should_auto_respond(parsed)
        self.assertFalse(result)

    def test_status_with_negative_sentiment_false(self):
        # "status" → status intent; "bad"/"stop" → sentiment=0.3, not > 0.6
        parsed = self.parser.parse("bad status, stop")
        result = self.parser.should_auto_respond(parsed)
        self.assertFalse(result)

    def test_neutral_message_returns_false(self):
        parsed = self.parser.parse("xyzzy blorp narf")
        result = self.parser.should_auto_respond(parsed)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
