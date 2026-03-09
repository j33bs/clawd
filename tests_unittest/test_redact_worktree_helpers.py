"""Tests for PATTERN regex in scripts/redact_worktree_hits.py.

Covers credential detection patterns:
- sk- API keys (OpenAI-style: 20+ consecutive alphanums)
- ghp_ GitHub personal tokens (exactly 36 chars)
- xox[baprs] Slack tokens (10+ chars after dash)
- AIza Google API keys (35 chars after AIza)
- -----BEGIN ... KEY----- PEM headers
- bearer <token> (20+ chars, case-insensitive)
- JWT format: eyJ[10+].[10+].[10+]
- No false positives on benign strings
- REPLACEMENT constant value
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "redact_worktree_hits.py"

_spec = _ilu.spec_from_file_location("redact_worktree_real", str(SCRIPT_PATH))
rw = _ilu.module_from_spec(_spec)
sys.modules["redact_worktree_real"] = rw
_spec.loader.exec_module(rw)

PATTERN = rw.PATTERN
REPLACEMENT = rw.REPLACEMENT


# ---------------------------------------------------------------------------
# sk- API keys
# ---------------------------------------------------------------------------


class TestPatternSkKeys(unittest.TestCase):
    """PATTERN matches sk- prefixed API keys (20+ consecutive alphanum)."""

    def test_sk_key_20_chars_matches(self):
        key = "sk-" + "A" * 20
        self.assertIsNotNone(PATTERN.search(key))

    def test_sk_key_40_chars_matches(self):
        key = "sk-" + "a1B2" * 10
        self.assertIsNotNone(PATTERN.search(key))

    def test_sk_key_19_chars_no_match(self):
        key = "sk-" + "A" * 19
        self.assertIsNone(PATTERN.search(key))

    def test_sk_key_in_context_matches(self):
        line = 'api_key = "sk-' + "x" * 25 + '"'
        self.assertIsNotNone(PATTERN.search(line))

    def test_sk_mixed_alphanum_matches(self):
        key = "sk-" + "aAbBcC123456789012XY"  # exactly 20 chars
        self.assertIsNotNone(PATTERN.search(key))


# ---------------------------------------------------------------------------
# ghp_ GitHub tokens
# ---------------------------------------------------------------------------


class TestPatternGhpTokens(unittest.TestCase):
    """PATTERN matches ghp_ GitHub personal tokens (exactly 36 alphanums)."""

    def test_ghp_36_chars_matches(self):
        token = "ghp_" + "A" * 36
        self.assertIsNotNone(PATTERN.search(token))

    def test_ghp_35_chars_no_match(self):
        token = "ghp_" + "A" * 35
        self.assertIsNone(PATTERN.search(token))

    def test_ghp_in_context_matches(self):
        # 6 * 6 = 36 alphanum chars
        line = "export GITHUB_TOKEN=ghp_" + "z1Y2x3" * 6
        self.assertIsNotNone(PATTERN.search(line))


# ---------------------------------------------------------------------------
# xox[baprs] Slack tokens
# ---------------------------------------------------------------------------


class TestPatternSlackTokens(unittest.TestCase):
    """PATTERN matches xox[baprs]-... Slack tokens (10+ chars after dash)."""

    def test_xoxb_matches(self):
        token = "xoxb-1234567890-abcdefghij"
        self.assertIsNotNone(PATTERN.search(token))

    def test_xoxa_matches(self):
        token = "xoxa-" + "a" * 15
        self.assertIsNotNone(PATTERN.search(token))

    def test_xoxp_matches(self):
        token = "xoxp-" + "b" * 15
        self.assertIsNotNone(PATTERN.search(token))

    def test_xoxr_matches(self):
        token = "xoxr-" + "c" * 15
        self.assertIsNotNone(PATTERN.search(token))

    def test_xoxs_matches(self):
        token = "xoxs-" + "d" * 15
        self.assertIsNotNone(PATTERN.search(token))

    def test_xoxb_short_no_match(self):
        # Only 9 chars after dash (needs 10+)
        token = "xoxb-123456789"
        self.assertIsNone(PATTERN.search(token))


# ---------------------------------------------------------------------------
# AIza Google API keys
# ---------------------------------------------------------------------------


class TestPatternGoogleApiKeys(unittest.TestCase):
    """PATTERN matches AIza... Google API keys (35 chars after AIza)."""

    def test_aiza_35_chars_matches(self):
        # 17 * 2 + 1 = 35 chars
        key = "AIza" + "A1" * 17 + "B"
        self.assertIsNotNone(PATTERN.search(key))

    def test_aiza_in_context_matches(self):
        line = "GOOGLE_API_KEY=AIza" + "0" * 35
        self.assertIsNotNone(PATTERN.search(line))


# ---------------------------------------------------------------------------
# PEM BEGIN KEY headers
# ---------------------------------------------------------------------------


class TestPatternPemHeaders(unittest.TestCase):
    """PATTERN matches -----BEGIN ... KEY----- PEM headers."""

    def test_begin_private_key_matches(self):
        self.assertIsNotNone(PATTERN.search("-----BEGIN PRIVATE KEY-----"))

    def test_begin_rsa_private_key_matches(self):
        self.assertIsNotNone(PATTERN.search("-----BEGIN RSA PRIVATE KEY-----"))

    def test_begin_ec_key_matches(self):
        self.assertIsNotNone(PATTERN.search("-----BEGIN EC KEY-----"))

    def test_begin_certificate_no_match(self):
        # "CERTIFICATE" does not contain the literal "KEY"
        result = PATTERN.search("-----BEGIN CERTIFICATE-----")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# bearer tokens
# ---------------------------------------------------------------------------


class TestPatternBearerTokens(unittest.TestCase):
    """PATTERN matches bearer <token> (20+ chars, case-insensitive)."""

    def test_bearer_lowercase_matches(self):
        line = "bearer " + "a" * 20
        self.assertIsNotNone(PATTERN.search(line))

    def test_bearer_uppercase_matches(self):
        line = "Bearer " + "A" * 20
        self.assertIsNotNone(PATTERN.search(line))

    def test_bearer_short_no_match(self):
        line = "bearer " + "a" * 19
        self.assertIsNone(PATTERN.search(line))

    def test_bearer_with_dots_dashes_matches(self):
        # Dots and dashes are in the token charset
        line = "Bearer " + "a.b-c_d" * 4
        self.assertIsNotNone(PATTERN.search(line))


# ---------------------------------------------------------------------------
# JWT format
# ---------------------------------------------------------------------------


class TestPatternJwt(unittest.TestCase):
    """PATTERN matches JWT format: eyJ[10+].[10+].[10+]."""

    def test_jwt_minimal_segments_matches(self):
        jwt = "eyJ" + "a" * 10 + "." + "b" * 10 + "." + "c" * 10
        self.assertIsNotNone(PATTERN.search(jwt))

    def test_jwt_real_format_matches(self):
        jwt = (
            "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk"
        )
        self.assertIsNotNone(PATTERN.search(jwt))

    def test_jwt_short_second_segment_no_match(self):
        # Second segment only 5 chars — fails {10,} minimum
        jwt = "eyJ" + "a" * 10 + "." + "b" * 5 + "." + "c" * 10
        self.assertIsNone(PATTERN.search(jwt))


# ---------------------------------------------------------------------------
# No false positives
# ---------------------------------------------------------------------------


class TestPatternNoFalsePositives(unittest.TestCase):
    """PATTERN does NOT match benign strings."""

    def test_random_text_no_match(self):
        self.assertIsNone(PATTERN.search("hello world this is normal text"))

    def test_short_sk_no_match(self):
        self.assertIsNone(PATTERN.search("sk-abc"))

    def test_empty_string_no_match(self):
        self.assertIsNone(PATTERN.search(""))

    def test_url_no_match(self):
        self.assertIsNone(PATTERN.search("https://example.com/api/v1/endpoint"))

    def test_number_sequence_no_match(self):
        self.assertIsNone(PATTERN.search("1234567890123456789012345"))


# ---------------------------------------------------------------------------
# REPLACEMENT constant
# ---------------------------------------------------------------------------


class TestReplacement(unittest.TestCase):
    """REPLACEMENT constant is the redaction placeholder."""

    def test_replacement_is_string(self):
        self.assertIsInstance(REPLACEMENT, str)

    def test_replacement_value(self):
        self.assertEqual(REPLACEMENT, "[REDACTED_SECRET]")

    def test_pattern_sub_redacts_sk_key(self):
        text = "key=sk-" + "x" * 25
        redacted = PATTERN.sub(REPLACEMENT, text)
        self.assertIn("[REDACTED_SECRET]", redacted)
        self.assertNotIn("sk-" + "x" * 25, redacted)

    def test_pattern_sub_preserves_context(self):
        text = "before sk-" + "X" * 20 + " after"
        redacted = PATTERN.sub(REPLACEMENT, text)
        self.assertIn("before", redacted)
        self.assertIn("after", redacted)


if __name__ == "__main__":
    unittest.main()
