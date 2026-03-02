import json
import os
import pathlib
import subprocess
import tempfile
import unittest


class ContractManagerTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(__file__).resolve().parents[1]
        self.ctl = self.root / "workspace" / "scripts" / "contractctl.py"
        self.mgr = self.root / "workspace" / "scripts" / "contract_manager.py"
        self.tmp = tempfile.TemporaryDirectory()
        self.state_dir = pathlib.Path(self.tmp.name) / "contract"
        self.env = os.environ.copy()
        self.env["OPENCLAW_CONTRACT_STATE_DIR"] = str(self.state_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, cmd):
        return subprocess.run(cmd, cwd=str(self.root), env=self.env, capture_output=True, text=True)

    def test_manual_override_ttl_persists_and_expires(self):
        proc = self._run([str(self.ctl), "set-mode", "CODE", "--ttl", "1m", "--reason", "test"])
        self.assertEqual(proc.returncode, 0, proc.stderr)

        proc = self._run([str(self.mgr)])
        self.assertEqual(proc.returncode, 0, proc.stderr)

        current_path = self.state_dir / "current.json"
        self.assertTrue(current_path.exists())
        cur = json.loads(current_path.read_text(encoding="utf-8"))
        self.assertEqual(cur["mode"], "CODE")
        self.assertIsNotNone(cur.get("override"))

        cur["override"]["ttl_until"] = "2000-01-01T00:00:00Z"
        current_path.write_text(json.dumps(cur, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        proc = self._run([str(self.mgr)])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cur2 = json.loads(current_path.read_text(encoding="utf-8"))
        self.assertIsNone(cur2.get("override"))


if __name__ == "__main__":
    unittest.main()
