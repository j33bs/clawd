import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestExchangeEnvelopeSchema(unittest.TestCase):
    def test_validate_detects_checksum_mismatch(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "workspace" / "scripts" / "exchange_envelope.py"
        self.assertTrue(script.exists())

        sample = next((repo_root / "workspace" / "exchanges" / "envelopes").glob("*.json"), None)
        self.assertIsNotNone(sample)
        payload = json.loads(sample.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as td:
            valid = Path(td) / "valid.json"
            valid.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            ok = subprocess.run(
                ["python3", str(script), "--validate", "--path", str(valid)],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ok.returncode, 0, ok.stdout + "\n" + ok.stderr)

            payload["body"] = payload["body"] + " tampered"
            invalid = Path(td) / "invalid.json"
            invalid.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            bad = subprocess.run(
                ["python3", str(script), "--validate", "--path", str(invalid)],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("checksum mismatch", bad.stdout + bad.stderr)


if __name__ == "__main__":
    unittest.main()
