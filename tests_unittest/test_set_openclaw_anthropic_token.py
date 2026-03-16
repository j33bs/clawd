import importlib.util as ilu
import json
import tempfile
import unittest
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "set_openclaw_anthropic_token.py"
_spec = ilu.spec_from_file_location("set_openclaw_anthropic_token_real", str(MODULE_PATH))
mod = ilu.module_from_spec(_spec)
sys.modules["set_openclaw_anthropic_token_real"] = mod
_spec.loader.exec_module(mod)


class TestSetOpenClawAnthropicToken(unittest.TestCase):
    def test_load_or_init_bootstraps_empty_shape(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "auth-profiles.json"
            data = mod.load_or_init(path)
            self.assertEqual(data["version"], 1)
            self.assertEqual(data["profiles"], {})
            self.assertEqual(data["order"], {})

    def test_update_anthropic_profile_writes_token_and_prioritizes(self):
        data = {
            "version": 1,
            "profiles": {
                "anthropic:default": {"provider": "anthropic", "type": "token", "token": "old"},
            },
            "order": {"anthropic": ["anthropic:default"]},
        }
        mod.update_anthropic_profile(
            data,
            profile_id="anthropic:manual",
            token="new-token",
            prioritize=True,
        )
        self.assertEqual(data["profiles"]["anthropic:manual"]["token"], "new-token")
        self.assertEqual(data["order"]["anthropic"][0], "anthropic:manual")
        self.assertIn("anthropic:default", data["order"]["anthropic"])

    def test_write_auth_file_round_trips_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "auth-profiles.json"
            payload = {"version": 1, "profiles": {}, "order": {}}
            mod.write_auth_file(path, payload)
            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(stored, payload)


if __name__ == "__main__":
    unittest.main()
