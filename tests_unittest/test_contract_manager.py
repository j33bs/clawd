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
        self.env.pop("OPENCLAW_CONTRACT_POLICY_PATH", None)

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

    def test_default_policy_file_is_loaded(self):
        proc = self._run([str(self.mgr)])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        current_path = self.state_dir / "current.json"
        cur = json.loads(current_path.read_text(encoding="utf-8"))
        policy = cur.get("policy", {})
        self.assertEqual(policy.get("service_rate_high"), 3.544)
        self.assertEqual(policy.get("service_rate_low"), 2.625)
        self.assertEqual(policy.get("idle_window_seconds"), 480)
        self.assertTrue(str(cur.get("policy_source", "")).endswith("workspace/governance/policy/contract_thresholds.json"))

    def test_env_policy_path_overrides_default(self):
        policy_path = pathlib.Path(self.tmp.name) / "policy_override.json"
        policy_path.write_text(
            json.dumps(
                {
                    "service_rate_high": 9.9,
                    "service_rate_low": 1.1,
                    "idle_window_seconds": 111,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.env["OPENCLAW_CONTRACT_POLICY_PATH"] = str(policy_path)
        proc = self._run([str(self.mgr)])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        current_path = self.state_dir / "current.json"
        cur = json.loads(current_path.read_text(encoding="utf-8"))
        policy = cur.get("policy", {})
        self.assertEqual(policy.get("service_rate_high"), 9.9)
        self.assertEqual(policy.get("service_rate_low"), 1.1)
        self.assertEqual(policy.get("idle_window_seconds"), 111)
        self.assertEqual(cur.get("policy_source"), str(policy_path))


class TestContractManagerPure(unittest.TestCase):
    """Unit tests for contract_manager pure functions — no subprocess."""

    def setUp(self):
        import importlib.util
        mgr_path = pathlib.Path(__file__).resolve().parents[1] / "workspace" / "scripts" / "contract_manager.py"
        spec = importlib.util.spec_from_file_location("contract_manager", mgr_path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    # --- parse_iso_z ---

    def test_parse_iso_z_z_suffix(self):
        result = self.mod.parse_iso_z("2026-03-08T12:00:00Z")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)

    def test_parse_iso_z_none_returns_none(self):
        self.assertIsNone(self.mod.parse_iso_z(None))

    def test_parse_iso_z_empty_returns_none(self):
        self.assertIsNone(self.mod.parse_iso_z(""))

    def test_parse_iso_z_invalid_returns_none(self):
        self.assertIsNone(self.mod.parse_iso_z("not-a-date"))

    def test_parse_iso_z_result_is_utc(self):
        import datetime
        result = self.mod.parse_iso_z("2026-03-08T00:00:00Z")
        self.assertEqual(result.tzinfo, datetime.timezone.utc)

    # --- normalize_policy_values ---

    def test_normalize_non_dict_returns_empty(self):
        self.assertEqual(self.mod.normalize_policy_values("string"), {})
        self.assertEqual(self.mod.normalize_policy_values(None), {})
        self.assertEqual(self.mod.normalize_policy_values([]), {})

    def test_normalize_window_minutes_cast_to_int(self):
        result = self.mod.normalize_policy_values({"window_minutes": "30"})
        self.assertEqual(result["window_minutes"], 30)
        self.assertIsInstance(result["window_minutes"], int)

    def test_normalize_alpha_cast_to_float(self):
        result = self.mod.normalize_policy_values({"alpha": "0.3"})
        self.assertAlmostEqual(result["alpha"], 0.3)

    def test_normalize_unknown_keys_ignored(self):
        result = self.mod.normalize_policy_values({"unknown_key": 99, "alpha": 0.5})
        self.assertNotIn("unknown_key", result)
        self.assertIn("alpha", result)

    def test_normalize_invalid_cast_skipped(self):
        result = self.mod.normalize_policy_values({"window_minutes": "not_an_int"})
        self.assertNotIn("window_minutes", result)

    def test_normalize_all_known_keys(self):
        payload = {
            "window_minutes": 5,
            "alpha": 0.9,
            "service_rate_high": 8.0,
            "service_rate_low": 2.0,
            "min_mode_minutes": 3,
            "interrupt_rate": 0.1,
            "idle_window_seconds": 60,
        }
        result = self.mod.normalize_policy_values(payload)
        self.assertEqual(len(result), 7)


if __name__ == "__main__":
    unittest.main()
