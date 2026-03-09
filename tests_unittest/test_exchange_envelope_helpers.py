"""Tests for pure helpers in workspace/scripts/exchange_envelope.py.

Covers:
- _utc_now() — ISO UTC timestamp ending in 'Z'
- _canonical_without_checksum(payload) — sorted JSON bytes minus checksum
- compute_checksum(payload) — SHA-256 hex digest of canonical form
- validate_payload(payload) — field + checksum validation
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "exchange_envelope.py"

_spec = _ilu.spec_from_file_location("exchange_envelope_real", str(SCRIPT_PATH))
_mod = _ilu.module_from_spec(_spec)
sys.modules["exchange_envelope_real"] = _mod
_spec.loader.exec_module(_mod)

_utc_now = _mod._utc_now
_canonical_without_checksum = _mod._canonical_without_checksum
compute_checksum = _mod.compute_checksum
validate_payload = _mod.validate_payload
REQUIRED_FIELDS = _mod.REQUIRED_FIELDS


def _valid_payload():
    """Build a structurally valid payload with correct checksum."""
    p = {
        "from_node": "sender",
        "to_node": "receiver",
        "utc": "2026-01-01T00:00:00Z",
        "subject": "test",
        "references": [],
        "body": "hello world",
    }
    p["checksum"] = compute_checksum(p)
    return p


# ---------------------------------------------------------------------------
# _utc_now
# ---------------------------------------------------------------------------


class TestUtcNow(unittest.TestCase):
    """Tests for _utc_now() — ISO UTC timestamp."""

    def test_returns_string(self):
        self.assertIsInstance(_utc_now(), str)

    def test_ends_with_z(self):
        self.assertTrue(_utc_now().endswith("Z"))

    def test_no_offset_string(self):
        self.assertNotIn("+00:00", _utc_now())

    def test_no_microseconds(self):
        ts = _utc_now()
        time_part = ts.split("T")[1].rstrip("Z")
        self.assertNotIn(".", time_part)

    def test_contains_t_separator(self):
        self.assertIn("T", _utc_now())


# ---------------------------------------------------------------------------
# _canonical_without_checksum
# ---------------------------------------------------------------------------


class TestCanonicalWithoutChecksum(unittest.TestCase):
    """Tests for _canonical_without_checksum() — sorted JSON bytes."""

    def test_returns_bytes(self):
        result = _canonical_without_checksum({"a": 1})
        self.assertIsInstance(result, bytes)

    def test_checksum_key_removed(self):
        payload = {"a": 1, "checksum": "abc123"}
        result = _canonical_without_checksum(payload)
        self.assertNotIn(b"checksum", result)

    def test_other_keys_present(self):
        payload = {"from_node": "x", "checksum": "ignore"}
        result = _canonical_without_checksum(payload)
        self.assertIn(b"from_node", result)

    def test_does_not_mutate_input(self):
        payload = {"a": 1, "checksum": "abc"}
        original = dict(payload)
        _canonical_without_checksum(payload)
        self.assertEqual(payload, original)

    def test_deterministic(self):
        payload = {"z": 2, "a": 1}
        a = _canonical_without_checksum(payload)
        b = _canonical_without_checksum(payload)
        self.assertEqual(a, b)

    def test_keys_sorted(self):
        # When keys are sorted, "a" comes before "z"
        payload = {"z": 2, "a": 1}
        result = _canonical_without_checksum(payload)
        idx_a = result.find(b'"a"')
        idx_z = result.find(b'"z"')
        self.assertLess(idx_a, idx_z)

    def test_no_checksum_key_in_output(self):
        # Payload without checksum field → still no checksum in output
        payload = {"body": "hello"}
        result = _canonical_without_checksum(payload)
        self.assertNotIn(b'"checksum"', result)


# ---------------------------------------------------------------------------
# compute_checksum
# ---------------------------------------------------------------------------


class TestComputeChecksum(unittest.TestCase):
    """Tests for compute_checksum() — SHA-256 hex digest."""

    def test_returns_string(self):
        self.assertIsInstance(compute_checksum({}), str)

    def test_returns_64_hex_chars(self):
        result = compute_checksum({"x": 1})
        self.assertEqual(len(result), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_deterministic(self):
        p = {"from_node": "a", "body": "hello"}
        self.assertEqual(compute_checksum(p), compute_checksum(p))

    def test_different_payloads_different_checksums(self):
        a = compute_checksum({"x": 1})
        b = compute_checksum({"x": 2})
        self.assertNotEqual(a, b)

    def test_ignores_existing_checksum_field(self):
        p1 = {"body": "hi"}
        p2 = {"body": "hi", "checksum": "stale_value"}
        # Both should produce the same checksum (checksum key excluded)
        self.assertEqual(compute_checksum(p1), compute_checksum(p2))


# ---------------------------------------------------------------------------
# validate_payload
# ---------------------------------------------------------------------------


class TestValidatePayload(unittest.TestCase):
    """Tests for validate_payload() — field and checksum validation."""

    def test_valid_payload_returns_true(self):
        ok, msg = validate_payload(_valid_payload())
        self.assertTrue(ok)

    def test_valid_payload_message_is_ok(self):
        ok, msg = validate_payload(_valid_payload())
        self.assertEqual(msg, "ok")

    def test_returns_tuple(self):
        result = validate_payload(_valid_payload())
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_missing_required_field_returns_false(self):
        p = _valid_payload()
        del p["body"]
        ok, msg = validate_payload(p)
        self.assertFalse(ok)

    def test_missing_field_error_mentions_field(self):
        p = _valid_payload()
        del p["subject"]
        ok, msg = validate_payload(p)
        self.assertIn("subject", msg)

    def test_references_not_list_returns_false(self):
        p = _valid_payload()
        p["references"] = "not a list"
        p["checksum"] = compute_checksum(p)
        ok, msg = validate_payload(p)
        self.assertFalse(ok)

    def test_bad_checksum_returns_false(self):
        p = _valid_payload()
        p["checksum"] = "deadbeef" * 8  # wrong but right length
        ok, msg = validate_payload(p)
        self.assertFalse(ok)

    def test_bad_checksum_error_mentions_mismatch(self):
        p = _valid_payload()
        p["checksum"] = "a" * 64
        ok, msg = validate_payload(p)
        self.assertIn("mismatch", msg)

    def test_all_required_fields_are_checked(self):
        for field in REQUIRED_FIELDS:
            if field == "checksum":
                continue  # checksum validated separately
            p = _valid_payload()
            del p[field]
            ok, _ = validate_payload(p)
            self.assertFalse(ok, f"Expected False when {field!r} is missing")


if __name__ == "__main__":
    unittest.main()
