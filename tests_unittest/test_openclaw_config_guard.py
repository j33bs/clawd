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


class TestImportedFunctions(unittest.TestCase):
    """Unit tests for pure functions in openclaw_config_guard — no subprocess needed."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "openclaw_config_guard", SCRIPT
        )
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    # --- _candidate_paths ---

    def test_candidate_paths_explicit_is_first(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            explicit = "/explicit/path/openclaw.json"
            paths = self.mod._candidate_paths(root, explicit)
            self.assertEqual(str(paths[0]), explicit)

    def test_candidate_paths_no_explicit_includes_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self.mod._candidate_paths(root, None)
            found = [str(p) for p in paths]
            self.assertTrue(any("workspace" in p for p in found))

    def test_candidate_paths_deduped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self.mod._candidate_paths(root, None)
            str_paths = [str(p) for p in paths]
            self.assertEqual(len(str_paths), len(set(str_paths)))

    def test_candidate_paths_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = self.mod._candidate_paths(root, None)
            self.assertIsInstance(result, list)

    # --- _enabled_entry_ids ---

    def test_enabled_entry_ids_empty_dict(self):
        result = self.mod._enabled_entry_ids({})
        self.assertEqual(result, [])

    def test_enabled_entry_ids_no_entries_key(self):
        result = self.mod._enabled_entry_ids({"allow": ["x"]})
        self.assertEqual(result, [])

    def test_enabled_entry_ids_entries_not_dict(self):
        result = self.mod._enabled_entry_ids({"entries": ["x", "y"]})
        self.assertEqual(result, [])

    def test_enabled_entry_dict_included(self):
        cfg = {"entries": {"my_plugin": {"enabled": True}}}
        result = self.mod._enabled_entry_ids(cfg)
        self.assertIn("my_plugin", result)

    def test_disabled_entry_excluded(self):
        cfg = {"entries": {"my_plugin": {"enabled": False}}}
        result = self.mod._enabled_entry_ids(cfg)
        self.assertNotIn("my_plugin", result)

    def test_bool_true_entry_included(self):
        cfg = {"entries": {"my_plugin": True}}
        result = self.mod._enabled_entry_ids(cfg)
        self.assertIn("my_plugin", result)

    def test_bool_false_entry_excluded(self):
        cfg = {"entries": {"my_plugin": False}}
        result = self.mod._enabled_entry_ids(cfg)
        self.assertNotIn("my_plugin", result)

    def test_missing_enabled_key_defaults_true(self):
        cfg = {"entries": {"my_plugin": {"version": "1.0"}}}
        result = self.mod._enabled_entry_ids(cfg)
        self.assertIn("my_plugin", result)

    # --- _ids_from_load_paths ---

    def test_ids_from_load_paths_empty(self):
        result = self.mod._ids_from_load_paths({})
        self.assertEqual(result, [])

    def test_ids_from_load_paths_no_load_key(self):
        result = self.mod._ids_from_load_paths({"allow": ["x"]})
        self.assertEqual(result, [])

    def test_ids_from_load_paths_extracts_stem(self):
        cfg = {"load": {"paths": ["/path/to/my_plugin.py"]}}
        result = self.mod._ids_from_load_paths(cfg)
        self.assertIn("my_plugin", result)

    def test_ids_from_load_paths_multiple(self):
        cfg = {"load": {"paths": ["/a/plugin_a.py", "/b/plugin_b.py"]}}
        result = self.mod._ids_from_load_paths(cfg)
        self.assertIn("plugin_a", result)
        self.assertIn("plugin_b", result)

    def test_ids_from_load_paths_non_string_skipped(self):
        cfg = {"load": {"paths": [42, None, "/ok/plugin.py"]}}
        result = self.mod._ids_from_load_paths(cfg)
        self.assertEqual(result, ["plugin"])

    # --- _normalized_allow ---

    def test_normalized_allow_none(self):
        allow, declared = self.mod._normalized_allow({})
        self.assertEqual(allow, [])
        self.assertFalse(declared)

    def test_normalized_allow_not_list(self):
        allow, declared = self.mod._normalized_allow({"allow": "a_string"})
        self.assertEqual(allow, [])
        self.assertFalse(declared)

    def test_normalized_allow_list_declared(self):
        _, declared = self.mod._normalized_allow({"allow": ["x"]})
        self.assertTrue(declared)

    def test_normalized_allow_deduped_and_sorted(self):
        cfg = {"allow": ["b_plugin", "a_plugin", "b_plugin"]}
        allow, _ = self.mod._normalized_allow(cfg)
        self.assertEqual(allow, ["a_plugin", "b_plugin"])

    def test_normalized_allow_strips_whitespace(self):
        cfg = {"allow": ["  my_plugin  "]}
        allow, _ = self.mod._normalized_allow(cfg)
        self.assertIn("my_plugin", allow)

    def test_normalized_allow_empty_strings_excluded(self):
        cfg = {"allow": ["", "  ", "valid_plugin"]}
        allow, _ = self.mod._normalized_allow(cfg)
        self.assertEqual(allow, ["valid_plugin"])

    # --- validate_config ---

    def test_validate_no_plugins_ok(self):
        result = self.mod.validate_config({})
        self.assertTrue(result["ok"])
        self.assertEqual(result["issues"], [])

    def test_validate_plugins_not_dict_ok(self):
        result = self.mod.validate_config({"plugins": "not_a_dict"})
        self.assertTrue(result["ok"])

    def test_validate_enabled_without_allow_fails(self):
        cfg = {"plugins": {"entries": {"my_plugin": {"enabled": True}}}}
        result = self.mod.validate_config(cfg)
        self.assertFalse(result["ok"])
        self.assertTrue(any("allow" in issue for issue in result["issues"]))

    def test_validate_allowlisted_plugin_passes(self):
        cfg = {
            "plugins": {
                "allow": ["my_plugin"],
                "entries": {"my_plugin": {"enabled": True}},
            }
        }
        result = self.mod.validate_config(cfg)
        self.assertTrue(result["ok"])
        self.assertEqual(result["issues"], [])

    def test_validate_not_allowlisted_fails(self):
        cfg = {
            "plugins": {
                "allow": ["other"],
                "entries": {"my_plugin": {"enabled": True}},
            }
        }
        result = self.mod.validate_config(cfg)
        self.assertFalse(result["ok"])
        self.assertIn("plugin_not_allowlisted:my_plugin", result["issues"])

    def test_validate_returns_enabled_plugins(self):
        cfg = {
            "plugins": {
                "allow": ["my_plugin"],
                "entries": {"my_plugin": {"enabled": True}},
            }
        }
        result = self.mod.validate_config(cfg)
        self.assertIn("my_plugin", result["enabled_plugins"])

    def test_validate_allow_declared_flag(self):
        cfg = {
            "plugins": {
                "allow": ["my_plugin"],
                "entries": {"my_plugin": {"enabled": True}},
            }
        }
        result = self.mod.validate_config(cfg)
        self.assertTrue(result["allow_declared"])


if __name__ == "__main__":
    unittest.main()
