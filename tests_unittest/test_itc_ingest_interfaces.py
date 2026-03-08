"""Tests for workspace/itc/ingest/interfaces.py pure helper functions.

Covers:
- iso_now_utc
- ts_token
- sha256_hex
- validate_signal (comprehensive — many branches)
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ITC_INGEST = REPO_ROOT / "workspace" / "itc" / "ingest"
if str(ITC_INGEST) not in sys.path:
    sys.path.insert(0, str(ITC_INGEST))

from interfaces import (  # noqa: E402
    _parse_iso,
    iso_now_utc,
    sha256_hex,
    ts_token,
    validate_signal,
)


def _valid_signal(**overrides):
    """Return a minimal valid signal dict, optionally overriding fields."""
    base = {
        "schema_version": 1,
        "source": "test",
        "ts_utc": "2026-01-15T12:00:00Z",
        "window": "1h",
        "metrics": {"sentiment": 0.5, "confidence": 0.8},
        "raw_ref": "workspace/raw/signal.json",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# iso_now_utc
# ---------------------------------------------------------------------------

class TestIsoNowUtc(unittest.TestCase):
    def test_returns_string(self):
        self.assertIsInstance(iso_now_utc(), str)

    def test_ends_with_z(self):
        self.assertTrue(iso_now_utc().endswith("Z"))

    def test_t_separator(self):
        self.assertIn("T", iso_now_utc())

    def test_length_is_20(self):
        # "YYYY-MM-DDTHH:MM:SSZ" = 20 chars
        self.assertEqual(len(iso_now_utc()), 20)


# ---------------------------------------------------------------------------
# ts_token
# ---------------------------------------------------------------------------

class TestTsToken(unittest.TestCase):
    def test_hyphens_removed(self):
        result = ts_token("2026-01-15T12:00:00Z")
        self.assertNotIn("-", result)

    def test_colons_removed(self):
        result = ts_token("2026-01-15T12:00:00Z")
        self.assertNotIn(":", result)

    def test_output_contains_digits_and_t_z(self):
        result = ts_token("2026-01-15T12:00:00Z")
        self.assertIn("T", result)
        self.assertIn("Z", result)
        self.assertIn("20260115", result)

    def test_returns_string(self):
        self.assertIsInstance(ts_token("2026-01-15T00:00:00Z"), str)


# ---------------------------------------------------------------------------
# sha256_hex
# ---------------------------------------------------------------------------

class TestSha256Hex(unittest.TestCase):
    def test_returns_string(self):
        self.assertIsInstance(sha256_hex(b"hello"), str)

    def test_length_is_64(self):
        self.assertEqual(len(sha256_hex(b"hello")), 64)

    def test_deterministic(self):
        self.assertEqual(sha256_hex(b"test"), sha256_hex(b"test"))

    def test_different_input_different_hash(self):
        self.assertNotEqual(sha256_hex(b"a"), sha256_hex(b"b"))

    def test_empty_bytes_known_hash(self):
        # SHA-256 of empty bytes is the known constant
        known = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        self.assertEqual(sha256_hex(b""), known)


# ---------------------------------------------------------------------------
# validate_signal — valid case
# ---------------------------------------------------------------------------

class TestValidateSignalValid(unittest.TestCase):
    def test_minimal_valid_signal(self):
        ok, reason = validate_signal(_valid_signal())
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_with_optional_signature(self):
        sig = "sha256:" + "a" * 64
        ok, reason = validate_signal(_valid_signal(signature=sig))
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_with_optional_regime_in_metrics(self):
        m = {"sentiment": 0.5, "confidence": 0.8, "regime": "risk_on"}
        ok, reason = validate_signal(_valid_signal(metrics=m))
        self.assertTrue(ok)

    def test_with_risk_on_off_in_metrics(self):
        m = {"sentiment": 0.5, "confidence": 0.8, "risk_on": 0.7, "risk_off": 0.3}
        ok, reason = validate_signal(_valid_signal(metrics=m))
        self.assertTrue(ok)

    def test_window_5m(self):
        ok, _ = validate_signal(_valid_signal(window="5m"))
        self.assertTrue(ok)

    def test_window_24h(self):
        ok, _ = validate_signal(_valid_signal(window="24h"))
        self.assertTrue(ok)

    def test_window_7d(self):
        ok, _ = validate_signal(_valid_signal(window="7d"))
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# validate_signal — invalid cases
# ---------------------------------------------------------------------------

class TestValidateSignalInvalid(unittest.TestCase):
    def test_not_dict_rejected(self):
        ok, reason = validate_signal("not a dict")
        self.assertFalse(ok)
        self.assertIn("not_object", reason)

    def test_missing_required_field(self):
        sig = _valid_signal()
        del sig["source"]
        ok, reason = validate_signal(sig)
        self.assertFalse(ok)
        self.assertIn("missing_required", reason)

    def test_wrong_schema_version(self):
        ok, reason = validate_signal(_valid_signal(schema_version=2))
        self.assertFalse(ok)
        self.assertIn("schema_version", reason)

    def test_empty_source_rejected(self):
        ok, reason = validate_signal(_valid_signal(source=""))
        self.assertFalse(ok)
        self.assertIn("source", reason)

    def test_non_string_source_rejected(self):
        ok, reason = validate_signal(_valid_signal(source=123))
        self.assertFalse(ok)
        self.assertIn("source", reason)

    def test_bad_ts_utc_rejected(self):
        ok, reason = validate_signal(_valid_signal(ts_utc="2026-01-15 12:00:00"))
        self.assertFalse(ok)
        self.assertIn("ts_utc", reason)

    def test_bad_window_rejected(self):
        ok, reason = validate_signal(_valid_signal(window="1week"))
        self.assertFalse(ok)
        self.assertIn("window", reason)

    def test_metrics_not_dict_rejected(self):
        ok, reason = validate_signal(_valid_signal(metrics="bad"))
        self.assertFalse(ok)
        self.assertIn("metrics", reason)

    def test_missing_sentiment_rejected(self):
        ok, reason = validate_signal(_valid_signal(metrics={"confidence": 0.5}))
        self.assertFalse(ok)
        self.assertIn("sentiment", reason)

    def test_missing_confidence_rejected(self):
        ok, reason = validate_signal(_valid_signal(metrics={"sentiment": 0.5}))
        self.assertFalse(ok)
        self.assertIn("confidence", reason)

    def test_sentiment_non_numeric_rejected(self):
        ok, reason = validate_signal(_valid_signal(metrics={"sentiment": "high", "confidence": 0.8}))
        self.assertFalse(ok)
        self.assertIn("sentiment", reason)

    def test_empty_raw_ref_rejected(self):
        ok, reason = validate_signal(_valid_signal(raw_ref=""))
        self.assertFalse(ok)
        self.assertIn("raw_ref", reason)

    def test_invalid_signature_format_rejected(self):
        ok, reason = validate_signal(_valid_signal(signature="bad-sig"))
        self.assertFalse(ok)
        self.assertIn("signature", reason)

    def test_unknown_top_level_key_rejected(self):
        s = _valid_signal()
        s["extra_key"] = "not_allowed"
        ok, reason = validate_signal(s)
        self.assertFalse(ok)
        self.assertIn("unknown_top_level", reason)

    def test_returns_tuple(self):
        result = validate_signal(_valid_signal())
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
