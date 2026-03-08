"""Tests for workspace/models/load_model.py pure helper functions.

Covers (no network, no subprocess, no mlx instantiation):
- _ensure_parent
- _parse_scalar
- _fallback_parse_registry
- normalize_role_spec
"""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.models.load_model import (  # noqa: E402
    _ensure_parent,
    _fallback_parse_registry,
    _parse_scalar,
    normalize_role_spec,
)


# ---------------------------------------------------------------------------
# _ensure_parent
# ---------------------------------------------------------------------------

class TestEnsureParent(unittest.TestCase):
    """Tests for _ensure_parent() — creates parent directory tree."""

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "a" / "b" / "c" / "file.json"
            _ensure_parent(path)
            self.assertTrue(path.parent.exists())

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nested" / "file.json"
            _ensure_parent(path)
            _ensure_parent(path)  # second call should not raise
            self.assertTrue(path.parent.exists())

    def test_existing_parent_ok(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "file.json"  # parent is td, already exists
            _ensure_parent(path)
            self.assertTrue(path.parent.exists())

    def test_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sub" / "file.json"
            _ensure_parent(path)
            self.assertFalse(path.exists())


# ---------------------------------------------------------------------------
# _parse_scalar
# ---------------------------------------------------------------------------

class TestParseScalar(unittest.TestCase):
    """Tests for _parse_scalar() — bool / int / float / str parsing."""

    def test_true_string(self):
        self.assertIs(_parse_scalar("true"), True)

    def test_true_upper(self):
        self.assertIs(_parse_scalar("True"), True)

    def test_false_string(self):
        self.assertIs(_parse_scalar("false"), False)

    def test_false_upper(self):
        self.assertIs(_parse_scalar("FALSE"), False)

    def test_integer(self):
        result = _parse_scalar("42")
        self.assertEqual(result, 42)
        self.assertIsInstance(result, int)

    def test_float(self):
        result = _parse_scalar("3.14")
        self.assertAlmostEqual(result, 3.14)
        self.assertIsInstance(result, float)

    def test_plain_string(self):
        result = _parse_scalar("hello")
        self.assertEqual(result, "hello")
        self.assertIsInstance(result, str)

    def test_empty_string(self):
        result = _parse_scalar("")
        self.assertEqual(result, "")

    def test_zero(self):
        self.assertEqual(_parse_scalar("0"), 0)

    def test_negative_passthrough(self):
        # "-5" has a leading dash so won't match .isdigit(); returned as str
        result = _parse_scalar("-5")
        self.assertIsInstance(result, str)

    def test_multi_dot_passthrough(self):
        # "1.2.3" has >1 dots → fallback to str
        result = _parse_scalar("1.2.3")
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# _fallback_parse_registry
# ---------------------------------------------------------------------------

class TestFallbackParseRegistry(unittest.TestCase):
    """Tests for _fallback_parse_registry() — YAML-like dict parser."""

    def test_simple_key_value(self):
        text = "router:\n  model: tinyllama:1.1b\n"
        result = _fallback_parse_registry(text)
        self.assertEqual(result["router"]["model"], "tinyllama:1.1b")

    def test_list_items(self):
        text = "models:\n  - alpha\n  - beta\n"
        result = _fallback_parse_registry(text)
        self.assertIn("alpha", result["models"])
        self.assertIn("beta", result["models"])

    def test_bool_value_parsed(self):
        text = "config:\n  enabled: true\n"
        result = _fallback_parse_registry(text)
        self.assertIs(result["config"]["enabled"], True)

    def test_int_value_parsed(self):
        text = "limits:\n  timeout: 30\n"
        result = _fallback_parse_registry(text)
        self.assertEqual(result["limits"]["timeout"], 30)

    def test_comment_stripped(self):
        text = "router:\n  model: tinyllama # router model\n"
        result = _fallback_parse_registry(text)
        self.assertNotIn("#", str(result["router"]["model"]))

    def test_blank_lines_skipped(self):
        text = "\nrouter:\n\n  model: x\n\n"
        result = _fallback_parse_registry(text)
        self.assertIn("router", result)

    def test_multiple_sections(self):
        text = "router:\n  model: r\nexperts:\n  coding: x\n"
        result = _fallback_parse_registry(text)
        self.assertIn("router", result)
        self.assertIn("experts", result)

    def test_empty_text_returns_empty_dict(self):
        result = _fallback_parse_registry("")
        self.assertIsInstance(result, dict)

    def test_returns_dict(self):
        self.assertIsInstance(_fallback_parse_registry("a:\n  b: 1\n"), dict)


# ---------------------------------------------------------------------------
# normalize_role_spec
# ---------------------------------------------------------------------------

class TestNormalizeRoleSpec(unittest.TestCase):
    """Tests for normalize_role_spec() — dict/str/other → {backend, model}."""

    def test_dict_with_backend_and_model(self):
        spec = normalize_role_spec({"backend": "mlx", "model": "gemma:2b"})
        self.assertEqual(spec["backend"], "mlx")
        self.assertEqual(spec["model"], "gemma:2b")

    def test_dict_missing_backend_uses_default(self):
        spec = normalize_role_spec({"model": "gemma:2b"}, default_backend="ollama")
        self.assertEqual(spec["backend"], "ollama")

    def test_dict_missing_model_uses_default(self):
        spec = normalize_role_spec({"backend": "ollama"}, default_model="tinyllama:1.1b")
        self.assertEqual(spec["model"], "tinyllama:1.1b")

    def test_string_value_uses_default_backend(self):
        spec = normalize_role_spec("gemma:2b", default_backend="ollama")
        self.assertEqual(spec["backend"], "ollama")
        self.assertEqual(spec["model"], "gemma:2b")

    def test_none_returns_defaults(self):
        spec = normalize_role_spec(None, default_backend="ollama", default_model="")
        self.assertEqual(spec["backend"], "ollama")
        self.assertEqual(spec["model"], "")

    def test_backend_lowercased(self):
        spec = normalize_role_spec({"backend": "MLX", "model": "x"})
        self.assertEqual(spec["backend"], "mlx")

    def test_model_stripped(self):
        spec = normalize_role_spec({"backend": "ollama", "model": "  qwen:2b  "})
        self.assertEqual(spec["model"], "qwen:2b")

    def test_returns_dict(self):
        self.assertIsInstance(normalize_role_spec("model"), dict)

    def test_empty_backend_uses_default(self):
        spec = normalize_role_spec({"backend": "", "model": "x"}, default_backend="ollama")
        self.assertEqual(spec["backend"], "ollama")


if __name__ == "__main__":
    unittest.main()
