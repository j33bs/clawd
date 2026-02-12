from __future__ import annotations

import unittest

from tools.validate_system1_evidence import validate


class ValidateSystem1EvidenceTests(unittest.TestCase):
    def test_accepts_required_keys_and_tolerates_unknown_keys(self) -> None:
        payload = {
            "gate_result": "pass",
            "completion_rate": 1.0,
            "traces": 3,
            "smoke_log_truncated": False,
            "extra_key": "ok",
        }
        self.assertEqual(validate(payload), [])

    def test_rejects_missing_or_invalid_required_keys(self) -> None:
        payload = {
            "gate_result": "maybe",
            "completion_rate": 1.2,
            "traces": -1,
            "smoke_log_truncated": "false",
        }
        errors = validate(payload)
        self.assertGreaterEqual(len(errors), 4)

    def test_rejects_non_object_payload(self) -> None:
        self.assertTrue(validate(["not", "an", "object"]))


if __name__ == "__main__":
    unittest.main()
