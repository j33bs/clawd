import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "workspace" / "scripts" / "contract_policy.py"


class TestContractPolicy(unittest.TestCase):
    def test_gpu_allowed_false_in_service_mode(self):
        with tempfile.TemporaryDirectory() as td:
            current = Path(td) / "current.json"
            current.write_text('{"mode":"SERVICE","source":"TEST"}\n', encoding="utf-8")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), "gpu-allowed", "--tool-id", "coder_vllm.models", "--contract", str(current)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0)
            payload = json.loads(run.stdout)
            self.assertFalse(payload["allowed"])
            self.assertEqual(payload["reason"], "policy_service_or_idle")

    def test_gpu_allowed_true_when_mode_code(self):
        with tempfile.TemporaryDirectory() as td:
            current = Path(td) / "current.json"
            current.write_text('{"mode":"CODE","source":"TEST"}\n', encoding="utf-8")
            env = dict(os.environ)
            env["OPENCLAW_CONTRACT_CURRENT"] = str(current)
            run = subprocess.run(
                [sys.executable, str(SCRIPT), "gpu-allowed", "--tool-id", "coder_vllm.models"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(run.returncode, 0)
            payload = json.loads(run.stdout)
            self.assertTrue(payload["allowed"])
            self.assertEqual(payload["reason"], "mode_code")


class TestContractPolicyPure(unittest.TestCase):
    """Unit tests for contract_policy pure functions — no subprocess."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("contract_policy", SCRIPT)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    # --- _parse_z ---

    def test_parse_z_none_returns_none(self):
        self.assertIsNone(self.mod._parse_z(None))

    def test_parse_z_empty_returns_none(self):
        self.assertIsNone(self.mod._parse_z(""))

    def test_parse_z_z_suffix_parsed(self):
        result = self.mod._parse_z("2026-03-08T00:00:00Z")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)

    def test_parse_z_invalid_returns_none(self):
        self.assertIsNone(self.mod._parse_z("not-a-date"))

    def test_parse_z_result_is_utc(self):
        import datetime as dt
        result = self.mod._parse_z("2026-03-08T00:00:00Z")
        self.assertEqual(result.tzinfo, dt.timezone.utc)

    # --- contract_allows_code ---

    def test_allows_code_when_mode_code(self):
        self.assertTrue(self.mod.contract_allows_code({"mode": "CODE"}))

    def test_allows_code_case_insensitive(self):
        self.assertTrue(self.mod.contract_allows_code({"mode": "code"}))

    def test_not_allows_code_when_service(self):
        self.assertFalse(self.mod.contract_allows_code({"mode": "SERVICE"}))

    def test_not_allows_code_empty_contract(self):
        self.assertFalse(self.mod.contract_allows_code({}))

    # --- contract_forces_code_override ---

    def test_override_mode_code_no_ttl_returns_true(self):
        contract = {"override": {"mode": "CODE"}}
        self.assertTrue(self.mod.contract_forces_code_override(contract))

    def test_override_not_dict_returns_false(self):
        self.assertFalse(self.mod.contract_forces_code_override({"override": "CODE"}))

    def test_override_mode_not_code_returns_false(self):
        contract = {"override": {"mode": "SERVICE"}}
        self.assertFalse(self.mod.contract_forces_code_override(contract))

    def test_override_expired_ttl_returns_false(self):
        past = "2020-01-01T00:00:00Z"
        contract = {"override": {"mode": "CODE", "ttl_until": past}}
        self.assertFalse(self.mod.contract_forces_code_override(contract))

    def test_override_future_ttl_returns_true(self):
        future = "2099-01-01T00:00:00Z"
        contract = {"override": {"mode": "CODE", "ttl_until": future}}
        self.assertTrue(self.mod.contract_forces_code_override(contract))

    def test_override_invalid_ttl_returns_false(self):
        contract = {"override": {"mode": "CODE", "ttl_until": "not-a-date"}}
        self.assertFalse(self.mod.contract_forces_code_override(contract))

    # --- gpu_tool_allowed_now ---

    def test_gpu_allowed_when_code_mode(self):
        result = self.mod.gpu_tool_allowed_now("my_tool", {"mode": "CODE"})
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "mode_code")

    def test_gpu_not_allowed_when_service_mode(self):
        result = self.mod.gpu_tool_allowed_now("my_tool", {"mode": "SERVICE"})
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "policy_service_or_idle")

    def test_gpu_allowed_when_forced_override(self):
        contract = {"mode": "SERVICE", "override": {"mode": "CODE"}}
        result = self.mod.gpu_tool_allowed_now("my_tool", contract)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "forced_code_override")

    def test_gpu_tool_id_in_result(self):
        result = self.mod.gpu_tool_allowed_now("coder_vllm", {"mode": "CODE"})
        self.assertEqual(result["tool_id"], "coder_vllm")

    def test_gpu_result_has_mode_field(self):
        result = self.mod.gpu_tool_allowed_now("tool", {"mode": "SERVICE"})
        self.assertIn("mode", result)


if __name__ == "__main__":
    unittest.main()
