import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "workspace" / "scripts" / "openclaw_config_guard.py"


class OpenClawConfigGuardTests(unittest.TestCase):
    def _run_guard(self, config: dict, strict: bool = True):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "openclaw.json"
            cfg.write_text(json.dumps(config), encoding="utf-8")
            cmd = [os.environ.get("PYTHON", "python3"), str(SCRIPT), "--config", str(cfg)]
            if strict:
                cmd.append("--strict")
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            payload = json.loads((proc.stdout or "{}").strip() or "{}")
            return proc.returncode, payload

    def test_deny_by_default_when_plugin_enabled_and_allow_missing(self):
        rc, payload = self._run_guard(
            {
                "plugins": {
                    "entries": {
                        "openclaw_secrets_plugin": {"enabled": True}
                    }
                }
            }
        )
        self.assertNotEqual(rc, 0)
        self.assertIn(
            "plugins.allow missing_or_empty while plugins are configured",
            payload.get("issues", []),
        )

    def test_allowlist_passes_for_enabled_plugin(self):
        rc, payload = self._run_guard(
            {
                "plugins": {
                    "allow": ["openclaw_secrets_plugin"],
                    "entries": {
                        "openclaw_secrets_plugin": {"enabled": True}
                    },
                }
            }
        )
        self.assertEqual(rc, 0)
        self.assertEqual(payload.get("issues"), [])

    def test_plugin_not_in_allowlist_fails(self):
        rc, payload = self._run_guard(
            {
                "plugins": {
                    "allow": ["trusted_plugin"],
                    "entries": {
                        "openclaw_secrets_plugin": {"enabled": True}
                    },
                }
            }
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("plugin_not_allowlisted:openclaw_secrets_plugin", payload.get("issues", []))


if __name__ == "__main__":
    unittest.main()
