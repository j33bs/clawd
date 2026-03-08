import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


class IdleReaperTest(unittest.TestCase):
    def test_idle_reaper_runs_noop_when_service_not_active(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            td_path = pathlib.Path(td)
            env = os.environ.copy()
            env["OPENCLAW_GPU_STATE_DIR"] = str(td_path / "gpu")
            env["OPENCLAW_CONTRACT_CURRENT"] = str(td_path / "contract" / "current.json")
            env["OPENCLAW_CONTRACT_EVENTS"] = str(td_path / "contract" / "events.jsonl")
            env["OPENCLAW_IDLE_REAPER_FORCE_SERVICE_INACTIVE"] = "1"

            proc = subprocess.run(
                [sys.executable, "workspace/scripts/idle_reaper.py"],
                cwd=str(root),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout.strip() or "{}")
            self.assertTrue(payload.get("ok"))
            self.assertEqual(payload.get("reason"), "service_not_active")
            events_path = td_path / "contract" / "events.jsonl"
            self.assertTrue(events_path.exists())
            lines = [line for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertGreaterEqual(len(lines), 1)
            event = json.loads(lines[-1])
            self.assertEqual(event.get("type"), "idle_reaper_action")
            self.assertEqual(event.get("reason"), "service_not_active")


class TestIdleReaperPure(unittest.TestCase):
    """Unit tests for idle_reaper pure functions — parse_z, utc_stamp, load/save json."""

    def setUp(self):
        import importlib.util
        from pathlib import Path
        script = Path(__file__).resolve().parents[1] / "workspace" / "scripts" / "idle_reaper.py"
        spec = importlib.util.spec_from_file_location("idle_reaper", script)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = pathlib.Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    # --- parse_z ---

    def test_parse_z_none_returns_none(self):
        self.assertIsNone(self.mod.parse_z(None))

    def test_parse_z_empty_returns_none(self):
        self.assertIsNone(self.mod.parse_z(""))

    def test_parse_z_z_suffix_parsed(self):
        result = self.mod.parse_z("2026-03-08T00:00:00Z")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)

    def test_parse_z_invalid_returns_none(self):
        self.assertIsNone(self.mod.parse_z("not-a-date"))

    def test_parse_z_utc_aware(self):
        import datetime
        result = self.mod.parse_z("2026-01-01T00:00:00Z")
        self.assertIsNotNone(result.tzinfo)

    # --- utc_stamp ---

    def test_utc_stamp_returns_string(self):
        result = self.mod.utc_stamp()
        self.assertIsInstance(result, str)

    def test_utc_stamp_ends_with_z(self):
        result = self.mod.utc_stamp()
        self.assertTrue(result.endswith("Z"))

    def test_utc_stamp_is_parseable(self):
        result = self.mod.utc_stamp()
        parsed = self.mod.parse_z(result)
        self.assertIsNotNone(parsed)

    # --- load_json / save_json ---

    def test_load_json_missing_returns_default(self):
        p = self.tmpdir / "missing.json"
        result = self.mod.load_json(p, {"default": True})
        self.assertEqual(result, {"default": True})

    def test_save_json_then_load_roundtrip(self):
        p = self.tmpdir / "data.json"
        self.mod.save_json(p, {"key": "value"})
        result = self.mod.load_json(p, {})
        self.assertEqual(result["key"], "value")

    def test_save_json_creates_parent_dirs(self):
        p = self.tmpdir / "sub" / "data.json"
        self.mod.save_json(p, {"x": 1})
        self.assertTrue(p.exists())

    def test_load_json_invalid_json_returns_default(self):
        p = self.tmpdir / "bad.json"
        p.write_text("not json", encoding="utf-8")
        result = self.mod.load_json(p, "fallback")
        self.assertEqual(result, "fallback")


if __name__ == "__main__":
    unittest.main()
