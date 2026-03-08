"""Tests for workspace/tacti/expression.py pure helpers.

Covers (no disk writes beyond tempfile, no real tacti.config):
- _load_manifest
- _cond_ok
"""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_tacti_stubs():
    tacti_pkg = types.ModuleType("tacti")
    tacti_pkg.__path__ = [str(REPO_ROOT / "workspace" / "tacti")]

    config_mod = types.ModuleType("tacti.config")
    config_mod.get_int = lambda key, default, clamp=None: default
    config_mod.get_float = lambda key, default, clamp=None: default
    config_mod.is_enabled = lambda key: False

    sys.modules.setdefault("tacti", tacti_pkg)
    sys.modules.setdefault("tacti.config", config_mod)


_build_tacti_stubs()

if str(REPO_ROOT / "workspace") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti import expression as ex  # noqa: E402


# ---------------------------------------------------------------------------
# _load_manifest
# ---------------------------------------------------------------------------

class TestLoadManifest(unittest.TestCase):
    """Tests for _load_manifest() — reads JSON feature list from a path."""

    def test_missing_path_returns_empty(self):
        result = ex._load_manifest(Path("/nonexistent/manifest.json"))
        self.assertEqual(result, [])

    def test_valid_list_returned(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.json"
            p.write_text(json.dumps([{"feature_name": "foo"}]), encoding="utf-8")
            result = ex._load_manifest(p)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["feature_name"], "foo")

    def test_dict_with_features_key(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.json"
            payload = {"features": [{"feature_name": "bar"}, {"feature_name": "baz"}]}
            p.write_text(json.dumps(payload), encoding="utf-8")
            result = ex._load_manifest(p)
            self.assertEqual(len(result), 2)

    def test_invalid_json_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.json"
            p.write_text("NOT JSON {{{{", encoding="utf-8")
            result = ex._load_manifest(p)
            self.assertEqual(result, [])

    def test_non_dict_items_filtered(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.json"
            p.write_text(json.dumps([{"feature_name": "ok"}, "not-a-dict", 42]), encoding="utf-8")
            result = ex._load_manifest(p)
            self.assertEqual(len(result), 1)

    def test_empty_list_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.json"
            p.write_text(json.dumps([]), encoding="utf-8")
            result = ex._load_manifest(p)
            self.assertEqual(result, [])

    def test_wrong_json_type_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.json"
            p.write_text(json.dumps("just a string"), encoding="utf-8")
            result = ex._load_manifest(p)
            self.assertEqual(result, [])

    def test_returns_list(self):
        result = ex._load_manifest(Path("/no/file"))
        self.assertIsInstance(result, list)


# ---------------------------------------------------------------------------
# _cond_ok
# ---------------------------------------------------------------------------

class TestCondOk(unittest.TestCase):
    """Tests for _cond_ok() — evaluates a single activation/suppression condition."""

    def test_none_cond_always_true(self):
        self.assertTrue(ex._cond_ok("time_of_day", None, {}))

    def test_unknown_name_returns_true(self):
        self.assertTrue(ex._cond_ok("unknown_condition", {"some": "val"}, {}))

    def test_time_of_day_in_range(self):
        result = ex._cond_ok("time_of_day", {"start": 8, "end": 18}, {"hour": 12})
        self.assertTrue(result)

    def test_time_of_day_out_of_range(self):
        result = ex._cond_ok("time_of_day", {"start": 8, "end": 18}, {"hour": 3})
        self.assertFalse(result)

    def test_time_of_day_at_boundary(self):
        self.assertTrue(ex._cond_ok("time_of_day", {"start": 8, "end": 18}, {"hour": 8}))
        self.assertTrue(ex._cond_ok("time_of_day", {"start": 8, "end": 18}, {"hour": 18}))

    def test_budget_remaining_pass(self):
        result = ex._cond_ok("budget_remaining_min", 0.5, {"budget_remaining": 0.8})
        self.assertTrue(result)

    def test_budget_remaining_fail(self):
        result = ex._cond_ok("budget_remaining_min", 0.9, {"budget_remaining": 0.2})
        self.assertFalse(result)

    def test_local_available_match_true(self):
        result = ex._cond_ok("local_available", True, {"local_available": True})
        self.assertTrue(result)

    def test_local_available_mismatch(self):
        result = ex._cond_ok("local_available", True, {"local_available": False})
        self.assertFalse(result)

    def test_arousal_min_pass(self):
        result = ex._cond_ok("arousal_min", 0.5, {"arousal": 0.9})
        self.assertTrue(result)

    def test_arousal_min_fail(self):
        result = ex._cond_ok("arousal_min", 0.8, {"arousal": 0.3})
        self.assertFalse(result)

    def test_valence_min_pass(self):
        result = ex._cond_ok("valence_min", 0.2, {"valence": 0.7})
        self.assertTrue(result)

    def test_valence_min_fail(self):
        result = ex._cond_ok("valence_min", 0.5, {"valence": 0.1})
        self.assertFalse(result)

    def test_valence_max_pass(self):
        result = ex._cond_ok("valence_max", 0.8, {"valence": 0.3})
        self.assertTrue(result)

    def test_valence_max_fail(self):
        result = ex._cond_ok("valence_max", 0.2, {"valence": 0.9})
        self.assertFalse(result)

    def test_returns_bool(self):
        result = ex._cond_ok("arousal_min", 0.5, {"arousal": 0.6})
        self.assertIsInstance(result, bool)

    def test_budget_default_context(self):
        # budget_remaining defaults to 1.0 if missing from context
        result = ex._cond_ok("budget_remaining_min", 0.5, {})
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
