"""Tests for scripts.exchange_envelope — compute_checksum, validate_payload, _canonical_without_checksum."""
import sys
import json
import hashlib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import exchange_envelope as ee


def _make_valid_payload(**overrides) -> dict:
    payload = {
        "from_node": "dali",
        "to_node": "z490",
        "utc": "2026-03-08T00:00:00Z",
        "subject": "test subject",
        "references": [],
        "body": "hello",
    }
    payload.update(overrides)
    # Compute checksum after setting fields
    payload["checksum"] = ee.compute_checksum(payload)
    return payload


class TestCanonicalWithoutChecksum(unittest.TestCase):
    """Tests for _canonical_without_checksum() — deterministic JSON bytes."""

    def test_returns_bytes(self):
        payload = {"a": 1, "checksum": "abc"}
        result = ee._canonical_without_checksum(payload)
        self.assertIsInstance(result, bytes)

    def test_checksum_key_removed(self):
        payload = {"a": 1, "checksum": "abc"}
        result = ee._canonical_without_checksum(payload)
        obj = json.loads(result)
        self.assertNotIn("checksum", obj)

    def test_other_keys_preserved(self):
        payload = {"a": 1, "b": 2, "checksum": "abc"}
        result = ee._canonical_without_checksum(payload)
        obj = json.loads(result)
        self.assertIn("a", obj)
        self.assertIn("b", obj)

    def test_keys_sorted(self):
        payload = {"z": 1, "a": 2, "m": 3}
        result = ee._canonical_without_checksum(payload)
        # JSON keys should appear in sorted order
        decoded = result.decode("utf-8")
        z_pos = decoded.index('"z"')
        a_pos = decoded.index('"a"')
        m_pos = decoded.index('"m"')
        self.assertLess(a_pos, m_pos)
        self.assertLess(m_pos, z_pos)

    def test_no_checksum_key_in_payload_ok(self):
        # Should not raise even if checksum not present
        payload = {"a": 1}
        result = ee._canonical_without_checksum(payload)
        obj = json.loads(result)
        self.assertEqual(obj, {"a": 1})

    def test_deterministic_for_same_input(self):
        payload = {"from_node": "a", "to_node": "b", "checksum": "x"}
        r1 = ee._canonical_without_checksum(payload)
        r2 = ee._canonical_without_checksum(payload)
        self.assertEqual(r1, r2)

    def test_different_for_different_input(self):
        p1 = {"body": "hello", "checksum": "x"}
        p2 = {"body": "world", "checksum": "x"}
        self.assertNotEqual(
            ee._canonical_without_checksum(p1),
            ee._canonical_without_checksum(p2),
        )


class TestComputeChecksum(unittest.TestCase):
    """Tests for compute_checksum() — SHA256 of canonical form."""

    def test_returns_string(self):
        result = ee.compute_checksum({"a": 1})
        self.assertIsInstance(result, str)

    def test_is_sha256_hex(self):
        result = ee.compute_checksum({"a": 1})
        self.assertEqual(len(result), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_deterministic(self):
        payload = {"from_node": "dali", "body": "hello"}
        self.assertEqual(ee.compute_checksum(payload), ee.compute_checksum(payload))

    def test_checksum_field_ignored(self):
        payload = {"a": 1, "checksum": "old_value"}
        payload2 = {"a": 1, "checksum": "different_value"}
        self.assertEqual(ee.compute_checksum(payload), ee.compute_checksum(payload2))

    def test_different_bodies_differ(self):
        c1 = ee.compute_checksum({"body": "hello"})
        c2 = ee.compute_checksum({"body": "world"})
        self.assertNotEqual(c1, c2)

    def test_matches_manual_sha256(self):
        payload = {"body": "hello", "checksum": "anything"}
        canonical = ee._canonical_without_checksum(payload)
        expected = hashlib.sha256(canonical).hexdigest()
        self.assertEqual(ee.compute_checksum(payload), expected)


class TestValidatePayload(unittest.TestCase):
    """Tests for validate_payload() — required fields + checksum integrity."""

    def test_valid_payload_returns_ok(self):
        payload = _make_valid_payload()
        ok, msg = ee.validate_payload(payload)
        self.assertTrue(ok)
        self.assertEqual(msg, "ok")

    def test_returns_tuple(self):
        payload = _make_valid_payload()
        result = ee.validate_payload(payload)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_missing_from_node_fails(self):
        payload = _make_valid_payload()
        del payload["from_node"]
        ok, msg = ee.validate_payload(payload)
        self.assertFalse(ok)
        self.assertIn("from_node", msg)

    def test_missing_to_node_fails(self):
        payload = _make_valid_payload()
        del payload["to_node"]
        ok, msg = ee.validate_payload(payload)
        self.assertFalse(ok)
        self.assertIn("to_node", msg)

    def test_missing_utc_fails(self):
        payload = _make_valid_payload()
        del payload["utc"]
        ok, msg = ee.validate_payload(payload)
        self.assertFalse(ok)

    def test_missing_subject_fails(self):
        payload = _make_valid_payload()
        del payload["subject"]
        ok, msg = ee.validate_payload(payload)
        self.assertFalse(ok)

    def test_missing_body_fails(self):
        payload = _make_valid_payload()
        del payload["body"]
        ok, msg = ee.validate_payload(payload)
        self.assertFalse(ok)

    def test_missing_checksum_fails(self):
        payload = _make_valid_payload()
        del payload["checksum"]
        ok, msg = ee.validate_payload(payload)
        self.assertFalse(ok)

    def test_wrong_checksum_fails(self):
        payload = _make_valid_payload()
        payload["checksum"] = "a" * 64  # valid hex length, wrong value
        ok, msg = ee.validate_payload(payload)
        self.assertFalse(ok)
        self.assertIn("mismatch", msg.lower())

    def test_references_not_list_fails(self):
        payload = _make_valid_payload()
        # Manually set references to a string and recompute
        payload["references"] = "not_a_list"
        payload["checksum"] = ee.compute_checksum(payload)
        ok, msg = ee.validate_payload(payload)
        self.assertFalse(ok)
        self.assertIn("references", msg)

    def test_empty_references_list_ok(self):
        payload = _make_valid_payload(references=[])
        # Recompute checksum since references changed
        payload["checksum"] = ee.compute_checksum(payload)
        ok, _ = ee.validate_payload(payload)
        self.assertTrue(ok)

    def test_non_empty_references_list_ok(self):
        payload = _make_valid_payload()
        payload["references"] = ["ref-1", "ref-2"]
        payload["checksum"] = ee.compute_checksum(payload)
        ok, _ = ee.validate_payload(payload)
        self.assertTrue(ok)

    def test_body_change_breaks_checksum(self):
        payload = _make_valid_payload()
        # Tamper with body without recomputing checksum
        payload["body"] = "tampered body content"
        ok, msg = ee.validate_payload(payload)
        self.assertFalse(ok)
        self.assertIn("mismatch", msg.lower())


class TestRequiredFields(unittest.TestCase):
    """Tests for REQUIRED_FIELDS constant."""

    def test_is_list(self):
        self.assertIsInstance(ee.REQUIRED_FIELDS, list)

    def test_non_empty(self):
        self.assertGreater(len(ee.REQUIRED_FIELDS), 0)

    def test_contains_checksum(self):
        self.assertIn("checksum", ee.REQUIRED_FIELDS)

    def test_contains_from_node(self):
        self.assertIn("from_node", ee.REQUIRED_FIELDS)

    def test_contains_to_node(self):
        self.assertIn("to_node", ee.REQUIRED_FIELDS)

    def test_contains_body(self):
        self.assertIn("body", ee.REQUIRED_FIELDS)

    def test_contains_references(self):
        self.assertIn("references", ee.REQUIRED_FIELDS)


if __name__ == "__main__":
    unittest.main()
