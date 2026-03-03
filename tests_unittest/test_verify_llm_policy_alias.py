import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = REPO_ROOT / "workspace" / "scripts" / "verify_llm_policy.sh"
POLICY_PATH = REPO_ROOT / "workspace" / "policy" / "llm_policy.json"


class TestVerifyLlmPolicyAlias(unittest.TestCase):
    def test_verify_llm_policy_accepts_legacy_provider_aliases(self):
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        governance_order = (
            policy.get("routing", {})
            .get("intents", {})
            .get("governance", {})
            .get("order", [])
        )
        self.assertIn("google-gemini-cli", governance_order)

        proc = subprocess.run(
            ["bash", str(VERIFY_SCRIPT)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        output = f"{proc.stdout}\n{proc.stderr}"
        self.assertEqual(proc.returncode, 0, output)
        self.assertIn("ok", output)

    def test_verify_llm_policy_still_rejects_unknown_provider(self):
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        policy["routing"]["intents"]["governance"]["order"] = ["definitely-unknown-provider"]

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tf:
            temp_path = Path(tf.name)
            json.dump(policy, tf)
            tf.write("\n")

        try:
            env = os.environ.copy()
            env["OPENCLAW_VERIFY_LLM_POLICY_PATH"] = str(temp_path)
            proc = subprocess.run(
                ["bash", str(VERIFY_SCRIPT)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                env=env,
            )
            output = f"{proc.stdout}\n{proc.stderr}"
            self.assertNotEqual(proc.returncode, 0, output)
            self.assertIn("unknown provider", output)
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
