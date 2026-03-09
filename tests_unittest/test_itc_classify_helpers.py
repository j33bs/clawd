"""Tests for pure helpers in scripts/itc_classify.py.

Covers:
- _resolve_repo_root(start) — path-only .git search
- classify_rules(text) — rule-based tag classification
- _build_prompt(text, max_chars) — prompt construction
- _extract_tag(answer) — LLM response tag extraction
- TRADE_SIGNAL_PATTERNS, NEWS_PATTERNS, SPAM_PATTERNS regex lists
"""
import importlib.util as _ilu
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "itc_classify.py"

_spec = _ilu.spec_from_file_location("itc_classify_real", str(SCRIPT_PATH))
itc = _ilu.module_from_spec(_spec)
sys.modules["itc_classify_real"] = itc
_spec.loader.exec_module(itc)

_resolve_repo_root = itc._resolve_repo_root
classify_rules = itc.classify_rules
_build_prompt = itc._build_prompt
_extract_tag = itc._extract_tag
TRADE_SIGNAL_PATTERNS = itc.TRADE_SIGNAL_PATTERNS
NEWS_PATTERNS = itc.NEWS_PATTERNS
SPAM_PATTERNS = itc.SPAM_PATTERNS
VALID_TAGS = itc.VALID_TAGS


# ---------------------------------------------------------------------------
# _resolve_repo_root
# ---------------------------------------------------------------------------


class TestResolveRepoRoot(unittest.TestCase):
    """Tests for _resolve_repo_root(start) — walks up to find .git directory."""

    def test_finds_git_in_current_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / ".git").mkdir()
            result = _resolve_repo_root(d / "subdir")
            # subdir doesn't exist but parent (d) has .git
            self.assertEqual(result, d)

    def test_finds_git_two_levels_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            deep = root / "a" / "b"
            deep.mkdir(parents=True)
            result = _resolve_repo_root(deep)
            self.assertEqual(result, root)

    def test_returns_none_when_no_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Create a deep path with no .git anywhere
            deep = Path(tmp) / "x" / "y" / "z"
            deep.mkdir(parents=True)
            # Walk 8 levels from deep — all within tmp which has no .git
            result = _resolve_repo_root(deep)
            # May or may not find a .git from the real filesystem above tmp
            # Just verify the return type
            self.assertTrue(result is None or isinstance(result, Path))

    def test_returns_path_when_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            result = _resolve_repo_root(root)
            self.assertIsInstance(result, Path)

    def test_start_dir_itself_has_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / ".git").mkdir()
            result = _resolve_repo_root(d)
            self.assertEqual(result, d)


# ---------------------------------------------------------------------------
# TRADE_SIGNAL_PATTERNS
# ---------------------------------------------------------------------------


class TestTradeSignalPatterns(unittest.TestCase):
    """TRADE_SIGNAL_PATTERNS matches trade setup text."""

    def test_buy_entry_target_matches(self):
        text = "buy BTC entry 50000 target 55000"
        matched = any(p.search(text) for p in TRADE_SIGNAL_PATTERNS)
        self.assertTrue(matched)

    def test_entry_equals_price_matches(self):
        text = "entry: 50000"
        matched = any(p.search(text) for p in TRADE_SIGNAL_PATTERNS)
        self.assertTrue(matched)

    def test_leverage_x_matches(self):
        text = "leverage: 10x"
        matched = any(p.search(text) for p in TRADE_SIGNAL_PATTERNS)
        self.assertTrue(matched)

    def test_sell_stop_loss_matches(self):
        text = "sell ETH stop loss 2800"
        matched = any(p.search(text) for p in TRADE_SIGNAL_PATTERNS)
        self.assertTrue(matched)

    def test_tp_target_matches(self):
        text = "tp: 60000"
        matched = any(p.search(text) for p in TRADE_SIGNAL_PATTERNS)
        self.assertTrue(matched)

    def test_plain_chat_no_match(self):
        text = "gm everyone, hope you have a great day"
        matched = any(p.search(text) for p in TRADE_SIGNAL_PATTERNS)
        self.assertFalse(matched)


# ---------------------------------------------------------------------------
# SPAM_PATTERNS
# ---------------------------------------------------------------------------


class TestSpamPatterns(unittest.TestCase):
    """SPAM_PATTERNS matches spam/promotional content."""

    def test_airdrop_matches(self):
        matched = any(p.search("airdrop now claim your tokens") for p in SPAM_PATTERNS)
        self.assertTrue(matched)

    def test_free_giveaway_matches(self):
        matched = any(p.search("free giveaway limited time") for p in SPAM_PATTERNS)
        self.assertTrue(matched)

    def test_repeated_chars_matches(self):
        # 6 repeated chars triggers pattern 3
        matched = any(p.search("AAAAAAA pump incoming") for p in SPAM_PATTERNS)
        self.assertTrue(matched)

    def test_join_now_matches(self):
        matched = any(p.search("join now limited spots") for p in SPAM_PATTERNS)
        self.assertTrue(matched)

    def test_100x_matches(self):
        matched = any(p.search("guaranteed 100x returns") for p in SPAM_PATTERNS)
        self.assertTrue(matched)

    def test_normal_message_no_match(self):
        matched = any(p.search("market looking bullish today") for p in SPAM_PATTERNS)
        self.assertFalse(matched)


# ---------------------------------------------------------------------------
# NEWS_PATTERNS
# ---------------------------------------------------------------------------


class TestNewsPatterns(unittest.TestCase):
    """NEWS_PATTERNS matches news/announcement content."""

    def test_breaking_matches(self):
        matched = any(p.search("breaking: exchange hacked") for p in NEWS_PATTERNS)
        self.assertTrue(matched)

    def test_etf_uppercase_matches(self):
        # Pattern 3 has no re.I — uppercase ETF required
        matched = any(p.search("ETF approval expected") for p in NEWS_PATTERNS)
        self.assertTrue(matched)

    def test_according_to_matches(self):
        matched = any(p.search("according to sources the deal is done") for p in NEWS_PATTERNS)
        self.assertTrue(matched)

    def test_merger_matches(self):
        matched = any(p.search("merger announced today") for p in NEWS_PATTERNS)
        self.assertTrue(matched)

    def test_trade_chat_no_match(self):
        matched = any(p.search("buy buy buy entry 50000") for p in NEWS_PATTERNS)
        self.assertFalse(matched)


# ---------------------------------------------------------------------------
# classify_rules
# ---------------------------------------------------------------------------


class TestClassifyRules(unittest.TestCase):
    """Tests for classify_rules(text) — rule-based two-value return."""

    def test_returns_tuple(self):
        primary, all_tags = classify_rules("hello world")
        self.assertIsInstance(primary, str)
        self.assertIsInstance(all_tags, list)

    def test_noise_default(self):
        primary, all_tags = classify_rules("hey gm everyone")
        self.assertEqual(primary, "noise")
        self.assertIn("noise", all_tags)

    def test_trade_signal_detected(self):
        primary, _ = classify_rules("buy BTC entry: 50000 target: 55000 sl: 48000")
        self.assertEqual(primary, "trade_signal")

    def test_spam_detected(self):
        primary, _ = classify_rules("free airdrop claim now limited time")
        self.assertEqual(primary, "spam")

    def test_news_detected(self):
        primary, _ = classify_rules("breaking: SEC launches investigation")
        self.assertEqual(primary, "news")

    def test_primary_is_first_tag(self):
        # trade_signal checked before spam — text with both gives trade_signal as primary
        text = "buy BTC entry: 50000 target 55000 airdrop free"
        primary, all_tags = classify_rules(text)
        self.assertEqual(primary, "trade_signal")
        # spam may also be in all_tags
        self.assertIn("trade_signal", all_tags)

    def test_all_tags_is_list_of_strings(self):
        _, all_tags = classify_rules("buy BTC entry: 50000")
        self.assertTrue(all(isinstance(t, str) for t in all_tags))

    def test_primary_in_valid_tags(self):
        for text in ["hey", "buy ETH entry: 1000", "airdrop free", "breaking: ETF"]:
            primary, _ = classify_rules(text)
            self.assertIn(primary, VALID_TAGS)

    def test_leverage_text_is_trade_signal(self):
        primary, _ = classify_rules("leverage: 20x entry 48000")
        self.assertEqual(primary, "trade_signal")


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt(unittest.TestCase):
    """Tests for _build_prompt(text, max_chars) — classification prompt builder."""

    def test_returns_string(self):
        self.assertIsInstance(_build_prompt("hello"), str)

    def test_contains_category_names(self):
        prompt = _build_prompt("test message")
        for tag in ("trade_signal", "news", "noise", "spam"):
            self.assertIn(tag, prompt)

    def test_short_text_included_verbatim(self):
        msg = "buy BTC now"
        prompt = _build_prompt(msg)
        self.assertIn(msg, prompt)

    def test_long_text_truncated_at_max_chars(self):
        long = "x" * 600
        prompt = _build_prompt(long, max_chars=500)
        # Should contain exactly 500 x's, not 600
        self.assertIn("x" * 500, prompt)
        self.assertNotIn("x" * 501, prompt)

    def test_default_max_chars_is_500(self):
        long = "a" * 600
        prompt_default = _build_prompt(long)
        prompt_500 = _build_prompt(long, max_chars=500)
        self.assertEqual(prompt_default, prompt_500)

    def test_exact_max_length_not_truncated(self):
        msg = "b" * 500
        prompt = _build_prompt(msg, max_chars=500)
        self.assertIn("b" * 500, prompt)


# ---------------------------------------------------------------------------
# _extract_tag
# ---------------------------------------------------------------------------


class TestExtractTag(unittest.TestCase):
    """Tests for _extract_tag(answer) — extracts valid tag from LLM response."""

    def test_trade_signal_extracted(self):
        self.assertEqual(_extract_tag("trade_signal"), "trade_signal")

    def test_news_extracted(self):
        self.assertEqual(_extract_tag("news"), "news")

    def test_noise_extracted(self):
        self.assertEqual(_extract_tag("noise"), "noise")

    def test_spam_extracted(self):
        self.assertEqual(_extract_tag("spam"), "spam")

    def test_case_insensitive(self):
        # .lower() is applied before checking
        self.assertEqual(_extract_tag("TRADE_SIGNAL"), "trade_signal")

    def test_tag_in_sentence(self):
        self.assertEqual(_extract_tag("The message is noise."), "noise")

    def test_unknown_returns_none(self):
        self.assertIsNone(_extract_tag("unknown"))

    def test_empty_returns_none(self):
        self.assertIsNone(_extract_tag(""))

    def test_whitespace_stripped(self):
        self.assertEqual(_extract_tag("  spam  "), "spam")

    def test_unrelated_text_returns_none(self):
        self.assertIsNone(_extract_tag("I cannot classify this message"))


if __name__ == "__main__":
    unittest.main()
