"""Tests for pure helpers in workspace/skills/mlx-infer/scripts/mlx_infer.py.

Pure stdlib (json, pathlib, sys, time) — no stubs needed.
Uses tempfile for load_config filesystem tests.

Covers:
- load_config() — None path, valid file, nonexistent path → SystemExit
- map_error() — OOM/MODEL_NOT_FOUND/INVALID_ARGS/RUNTIME classification
- approx_tokens() — word count approximation
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MLX_INFER_PATH = REPO_ROOT / "workspace" / "skills" / "mlx-infer" / "scripts" / "mlx_infer.py"

_spec = _ilu.spec_from_file_location("mlx_infer_real", str(MLX_INFER_PATH))
mi = _ilu.module_from_spec(_spec)
sys.modules["mlx_infer_real"] = mi
_spec.loader.exec_module(mi)


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

class TestLoadConfig(unittest.TestCase):
    """Tests for load_config() — JSON config reader."""

    def test_returns_empty_dict_for_none(self):
        result = mi.load_config(None)
        self.assertEqual(result, {})

    def test_returns_empty_dict_for_empty_string(self):
        result = mi.load_config("")
        self.assertEqual(result, {})

    def test_returns_parsed_json_for_valid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.json"
            cfg.write_text(json.dumps({"default_model": "llama"}), encoding="utf-8")
            result = mi.load_config(str(cfg))
        self.assertEqual(result["default_model"], "llama")

    def test_returns_dict_for_valid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.json"
            cfg.write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")
            result = mi.load_config(str(cfg))
        self.assertIsInstance(result, dict)

    def test_raises_system_exit_for_missing_file(self):
        """load_config calls emit() which raises SystemExit when file missing."""
        with self.assertRaises(SystemExit):
            mi.load_config("/tmp/nonexistent_config_xyz_abc.json")

    def test_falsy_path_returns_empty(self):
        for falsy in (None, "", 0, False):
            result = mi.load_config(falsy)
            self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# map_error
# ---------------------------------------------------------------------------

class TestMapError(unittest.TestCase):
    """Tests for map_error() — exception → error code string."""

    def test_oom_on_out_of_memory(self):
        result = mi.map_error(RuntimeError("out of memory"))
        self.assertEqual(result, "OOM")

    def test_oom_on_oom(self):
        result = mi.map_error(RuntimeError("OOM occurred"))
        self.assertEqual(result, "OOM")

    def test_oom_on_cannot_allocate_memory(self):
        result = mi.map_error(MemoryError("cannot allocate memory for tensor"))
        self.assertEqual(result, "OOM")

    def test_model_not_found_on_not_found(self):
        result = mi.map_error(RuntimeError("model not found"))
        self.assertEqual(result, "MODEL_NOT_FOUND")

    def test_model_not_found_on_no_such_file(self):
        result = mi.map_error(FileNotFoundError("no such file or directory"))
        self.assertEqual(result, "MODEL_NOT_FOUND")

    def test_model_not_found_on_cannot_find(self):
        result = mi.map_error(RuntimeError("cannot find model weights"))
        self.assertEqual(result, "MODEL_NOT_FOUND")

    def test_invalid_args_on_value_error(self):
        result = mi.map_error(ValueError("bad argument"))
        self.assertEqual(result, "INVALID_ARGS")

    def test_runtime_for_generic_exception(self):
        result = mi.map_error(RuntimeError("something unexpected happened"))
        self.assertEqual(result, "RUNTIME")

    def test_runtime_for_type_error(self):
        result = mi.map_error(TypeError("wrong type"))
        self.assertEqual(result, "RUNTIME")

    def test_returns_string(self):
        result = mi.map_error(Exception("x"))
        self.assertIsInstance(result, str)

    def test_case_insensitive_oom_check(self):
        """'Out of Memory' (mixed case) → OOM via .lower()."""
        result = mi.map_error(RuntimeError("Out of Memory"))
        self.assertEqual(result, "OOM")


# ---------------------------------------------------------------------------
# approx_tokens
# ---------------------------------------------------------------------------

class TestApproxTokens(unittest.TestCase):
    """Tests for approx_tokens() — word-count approximation."""

    def test_returns_int(self):
        result = mi.approx_tokens("hello world")
        self.assertIsInstance(result, int)

    def test_single_word(self):
        result = mi.approx_tokens("hello")
        self.assertEqual(result, 1)

    def test_two_words(self):
        result = mi.approx_tokens("hello world")
        self.assertEqual(result, 2)

    def test_extra_spaces_ignored(self):
        result = mi.approx_tokens("  hello   world  ")
        self.assertEqual(result, 2)

    def test_empty_string_returns_one(self):
        """max(1, len(parts)) ensures minimum of 1."""
        result = mi.approx_tokens("")
        self.assertEqual(result, 1)

    def test_whitespace_only_returns_one(self):
        result = mi.approx_tokens("   ")
        self.assertEqual(result, 1)

    def test_multiline_text(self):
        text = "line one\nline two\nline three"
        result = mi.approx_tokens(text)
        self.assertEqual(result, 6)

    def test_larger_text_word_count(self):
        words = ["word"] * 20
        result = mi.approx_tokens(" ".join(words))
        self.assertEqual(result, 20)


if __name__ == "__main__":
    unittest.main()
