"""Tests for pure helpers in workspace/itc/ingest/interfaces.py.

All stdlib — no network, no external deps.

Covers:
- iso_now_utc
- ts_token
- sha256_hex
- _parse_iso
- validate_signal
"""
import importlib.util as _ilu
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ITC_INGEST_DIR = REPO_ROOT / "workspace" / "itc" / "ingest"

_spec = _ilu.spec_from_file_location(
    "itc_interfaces_mod",
    str(ITC_INGEST_DIR / "interfaces.py"),
)
_mod = _ilu.module_from_spec(_spec)
sys.modules["itc_interfaces_mod"] = _mod
_spec.loader.exec_module(_mod)

iso_now_utc = _mod.iso_now_utc
ts_token = _mod.ts_token
sha256_hex = _mod.sha256_hex
_parse_iso = _mod._parse_iso
validate_signal = _mod.validate_signal


def _minimal_signal(**overrides):
    """Return a minimal valid ITC signal dict."""
    base = {
        "schema_version": 1,
        "source": "test",
        "ts_utc": "2026-03-07T12:00:00Z",
        "window": "1h",
        "metrics": {"sentiment": 0.5, "confidence": 0.8},
        "raw_ref": "msg:12345",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# iso_now_utc
# ---------------------------------------------------------------------------

class TestIsoNowUtc(unittest.TestCase):
    """Tests for iso_now_utc() — UTC ISO timestamp with Z suffix."""

    def test_returns_string(self):
        self.assertIsInstance(iso_now_utc(), str)

    def test_ends_with_z(self):
        self.assertTrue(iso_now_utc().endswith("Z"))

    def test_parseable(self):
        result = iso_now_utc()
        datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# ts_token
# ---------------------------------------------------------------------------

class TestTsToken(unittest.TestCase):
    """Tests for ts_token() — strip separators from ISO timestamp."""

    def test_strips_hyphens_and_colons(self):
        result = ts_token("2026-03-07T12:00:00Z")
        self.assertNotIn("-", result)
        self.assertNotIn(":", result)

    def test_expected_output(self):
        result = ts_token("2026-03-07T12:00:00Z")
        self.assertEqual(result, "20260307T120000Z")

    def test_returns_string(self):
        self.assertIsInstance(ts_token("2026-01-01T00:00:00Z"), str)

    def test_empty_string(self):
        self.assertEqual(ts_token(""), "")


# ---------------------------------------------------------------------------
# sha256_hex
# ---------------------------------------------------------------------------

class TestSha256Hex(unittest.TestCase):
    """Tests for sha256_hex() — SHA-256 hex digest of bytes."""

    def test_returns_string(self):
        self.assertIsInstance(sha256_hex(b"hello"), str)

    def test_length_64(self):
        result = sha256_hex(b"any content")
        self.assertEqual(len(result), 64)

    def test_deterministic(self):
        a = sha256_hex(b"same content")
        b = sha256_hex(b"same content")
        self.assertEqual(a, b)

    def test_different_inputs_differ(self):
        a = sha256_hex(b"input_a")
        b = sha256_hex(b"input_b")
        self.assertNotEqual(a, b)

    def test_empty_bytes(self):
        result = sha256_hex(b"")
        self.assertEqual(len(result), 64)


# ---------------------------------------------------------------------------
# _parse_iso
# ---------------------------------------------------------------------------

class TestParseIso(unittest.TestCase):
    """Tests for _parse_iso() — parse UTC ISO timestamp string."""

    def test_returns_datetime(self):
        result = _parse_iso("2026-03-07T12:00:00Z")
        self.assertIsInstance(result, datetime)

    def test_correct_components(self):
        result = _parse_iso("2026-03-07T15:30:45Z")
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.day, 7)
        self.assertEqual(result.hour, 15)
        self.assertEqual(result.minute, 30)
        self.assertEqual(result.second, 45)

    def test_is_utc(self):
        result = _parse_iso("2026-01-01T00:00:00Z")
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_invalid_format_raises(self):
        with self.assertRaises(ValueError):
            _parse_iso("not-a-date")


# ---------------------------------------------------------------------------
# validate_signal
# ---------------------------------------------------------------------------

class TestValidateSignal(unittest.TestCase):
    """Tests for validate_signal() — ITC signal schema validation."""

    def test_valid_minimal_signal(self):
        ok, reason = validate_signal(_minimal_signal())
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_not_a_dict(self):
        ok, reason = validate_signal("not a dict")
        self.assertFalse(ok)
        self.assertEqual(reason, "signal_not_object")

    def test_missing_required_field(self):
        sig = _minimal_signal()
        del sig["source"]
        ok, reason = validate_signal(sig)
        self.assertFalse(ok)
        self.assertIn("missing_required", reason)

    def test_wrong_schema_version(self):
        ok, reason = validate_signal(_minimal_signal(schema_version=2))
        self.assertFalse(ok)
        self.assertEqual(reason, "schema_version_invalid")

    def test_invalid_ts_utc(self):
        ok, reason = validate_signal(_minimal_signal(ts_utc="2026-03-07 12:00:00"))
        self.assertFalse(ok)
        self.assertEqual(reason, "ts_utc_invalid")

    def test_invalid_window(self):
        ok, reason = validate_signal(_minimal_signal(window="invalid"))
        self.assertFalse(ok)
        self.assertEqual(reason, "window_invalid")

    def test_valid_window_formats(self):
        for w in ("1m", "30h", "7d"):
            ok, reason = validate_signal(_minimal_signal(window=w))
            self.assertTrue(ok, f"window {w!r} should be valid but got: {reason}")

    def test_metrics_not_dict(self):
        ok, reason = validate_signal(_minimal_signal(metrics="bad"))
        self.assertFalse(ok)
        self.assertEqual(reason, "metrics_invalid")

    def test_metrics_missing_sentiment(self):
        sig = _minimal_signal()
        del sig["metrics"]["sentiment"]
        ok, reason = validate_signal(sig)
        self.assertFalse(ok)
        self.assertIn("sentiment", reason)

    def test_unknown_top_level_key(self):
        sig = _minimal_signal()
        sig["unknown_key"] = "value"
        ok, reason = validate_signal(sig)
        self.assertFalse(ok)
        self.assertIn("unknown_top_level_keys", reason)

    def test_valid_with_optional_signature(self):
        sig = _minimal_signal()
        sig["signature"] = "sha256:" + "a" * 64
        ok, reason = validate_signal(sig)
        self.assertTrue(ok)

    def test_invalid_signature_format(self):
        sig = _minimal_signal()
        sig["signature"] = "bad-sig"
        ok, reason = validate_signal(sig)
        self.assertFalse(ok)
        self.assertEqual(reason, "signature_invalid")

    def test_empty_source_invalid(self):
        ok, reason = validate_signal(_minimal_signal(source=""))
        self.assertFalse(ok)
        self.assertEqual(reason, "source_invalid")

    def test_returns_tuple(self):
        result = validate_signal(_minimal_signal())
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
