import importlib.util
import json
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path


def _load_policy_router_module():
    repo_root = Path(__file__).resolve().parents[1]
    mod_path = repo_root / "workspace" / "scripts" / "policy_router.py"
    spec = importlib.util.spec_from_file_location("policy_router", str(mod_path))
    assert spec and spec.loader, f"Failed to load module spec for {mod_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestLlmPolicySchemaValidation(unittest.TestCase):
    def test_invalid_policy_typo_fails_closed_by_default(self):
        policy_router = _load_policy_router_module()
        policy_router.log_event = lambda *args, **kwargs: None

        bad_policy = {
            "version": 2,
            "budgets": {
                "intents": {
                    "itc_classify": {
                        "dailyTokenBudgte": 25000
                    }
                }
            }
        }

        with tempfile.TemporaryDirectory() as td:
            policy_path = Path(td) / "llm_policy.json"
            policy_path.write_text(json.dumps(bad_policy), encoding="utf-8")

            with self.assertRaises(policy_router.PolicyValidationError):
                policy_router.load_policy(policy_path)

    def test_invalid_policy_typo_allowed_when_strict_disabled(self):
        policy_router = _load_policy_router_module()
        policy_router.log_event = lambda *args, **kwargs: None

        bad_policy = {
            "version": 2,
            "budgets": {
                "intents": {
                    "itc_classify": {
                        "dailyTokenBudgte": 25000
                    }
                }
            }
        }

        with tempfile.TemporaryDirectory() as td:
            policy_path = Path(td) / "llm_policy.json"
            policy_path.write_text(json.dumps(bad_policy), encoding="utf-8")

            with unittest.mock.patch.dict(os.environ, {"OPENCLAW_POLICY_STRICT": "0"}, clear=False):
                loaded = policy_router.load_policy(policy_path)

            self.assertEqual(loaded.get("version"), 2)
            intent_budget = loaded.get("budgets", {}).get("intents", {}).get("itc_classify", {})
            self.assertIn("dailyTokenBudget", intent_budget)
            self.assertIn("dailyTokenBudgte", intent_budget)


if __name__ == "__main__":
    unittest.main()
