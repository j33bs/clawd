import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestInv003Scaffold(unittest.TestCase):
    def test_schema_exists_and_has_required_keys(self):
        repo_root = Path(__file__).resolve().parents[1]
        schema_path = repo_root / "workspace" / "scripts" / "inv_003_scaffold" / "results.schema.json"
        self.assertTrue(schema_path.exists())
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        required = set(schema.get("required", []))
        self.assertTrue({"run_id", "timestamp_utc", "mode", "prompts", "comparisons", "summary"}.issubset(required))

    def test_runner_dry_run_generates_placeholder_output(self):
        repo_root = Path(__file__).resolve().parents[1]
        runner = repo_root / "workspace" / "scripts" / "inv_003_scaffold" / "run_inv_003.py"
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "inv003_result.json"
            proc = subprocess.run(
                ["python3", str(runner), "--dry-run", "--run-id", "inv003-test", "--output", str(out_path), "--json"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("run_id"), "inv003-test")
            self.assertEqual(payload.get("mode"), "dry_run")
            self.assertIn("comparisons", payload)


if __name__ == "__main__":
    unittest.main()

