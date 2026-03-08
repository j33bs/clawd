"""Tests for pure helpers in workspace/models/mlx_backend.py.

No MLX hardware needed — only tests functions that don't require mlx_lm.
Module loads cleanly because _import_mlx_modules() is inside MlxBackend.__init__,
not at module level.

Covers:
- estimate_tokens() — character-count approximation (len/4, min 1)
- MlxGenerationResult dataclass — field types and construction
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MLX_BACKEND_PATH = REPO_ROOT / "workspace" / "models" / "mlx_backend.py"

_spec = _ilu.spec_from_file_location("mlx_backend_real", str(MLX_BACKEND_PATH))
mlx = _ilu.module_from_spec(_spec)
sys.modules["mlx_backend_real"] = mlx
_spec.loader.exec_module(mlx)


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------

class TestEstimateTokens(unittest.TestCase):
    """Tests for estimate_tokens() — character-count token approximation."""

    def test_returns_int(self):
        result = mlx.estimate_tokens("hello world")
        self.assertIsInstance(result, int)

    def test_empty_string_returns_zero(self):
        result = mlx.estimate_tokens("")
        self.assertEqual(result, 0)

    def test_none_treated_as_empty(self):
        """str(text or '') converts None → '' → 0."""
        result = mlx.estimate_tokens(None)
        self.assertEqual(result, 0)

    def test_four_chars_returns_one(self):
        result = mlx.estimate_tokens("abcd")  # 4 / 4 = 1
        self.assertEqual(result, 1)

    def test_eight_chars_returns_two(self):
        result = mlx.estimate_tokens("abcdefgh")  # 8 / 4 = 2
        self.assertEqual(result, 2)

    def test_one_char_returns_one(self):
        """max(1, ...) ensures result >= 1 for non-empty input."""
        result = mlx.estimate_tokens("a")  # 1 / 4 = 0 → max(1, 0) = 1
        self.assertEqual(result, 1)

    def test_three_chars_returns_one(self):
        result = mlx.estimate_tokens("abc")  # int(3/4) = 0 → max(1, 0) = 1
        self.assertEqual(result, 1)

    def test_larger_text_scales_with_length(self):
        text = "x" * 400  # 400 / 4 = 100
        result = mlx.estimate_tokens(text)
        self.assertEqual(result, 100)

    def test_non_ascii_chars_counted_by_len(self):
        text = "αβγδ"  # 4 unicode chars → len=4 → 4/4=1
        result = mlx.estimate_tokens(text)
        self.assertGreaterEqual(result, 1)

    def test_whitespace_only_non_empty(self):
        result = mlx.estimate_tokens("    ")  # 4 chars / 4 = 1
        self.assertEqual(result, 1)


# ---------------------------------------------------------------------------
# MlxGenerationResult
# ---------------------------------------------------------------------------

class TestMlxGenerationResult(unittest.TestCase):
    """Tests for MlxGenerationResult dataclass."""

    def _make_result(self, **kwargs):
        defaults = {
            "text": "The answer is 42.",
            "latency_ms": 250,
            "backend": "mlx",
            "model": "mlx-community/Mistral-7B",
            "tokens_in": 20,
            "tokens_out": 30,
            "total_tokens": 50,
            "error": None,
        }
        defaults.update(kwargs)
        return mlx.MlxGenerationResult(**defaults)

    def test_creates_instance(self):
        result = self._make_result()
        self.assertIsInstance(result, mlx.MlxGenerationResult)

    def test_text_field(self):
        result = self._make_result(text="hello")
        self.assertEqual(result.text, "hello")

    def test_latency_ms_field(self):
        result = self._make_result(latency_ms=100)
        self.assertEqual(result.latency_ms, 100)

    def test_backend_field(self):
        result = self._make_result(backend="mlx")
        self.assertEqual(result.backend, "mlx")

    def test_model_field(self):
        result = self._make_result(model="mistral")
        self.assertEqual(result.model, "mistral")

    def test_tokens_in_field(self):
        result = self._make_result(tokens_in=15)
        self.assertEqual(result.tokens_in, 15)

    def test_tokens_out_field(self):
        result = self._make_result(tokens_out=25)
        self.assertEqual(result.tokens_out, 25)

    def test_total_tokens_field(self):
        result = self._make_result(total_tokens=40)
        self.assertEqual(result.total_tokens, 40)

    def test_error_none(self):
        result = self._make_result(error=None)
        self.assertIsNone(result.error)

    def test_error_string(self):
        result = self._make_result(error="OOM")
        self.assertEqual(result.error, "OOM")

    def test_all_required_fields_accessible(self):
        result = self._make_result()
        for field in ("text", "latency_ms", "backend", "model",
                      "tokens_in", "tokens_out", "total_tokens", "error"):
            self.assertTrue(hasattr(result, field))


if __name__ == "__main__":
    unittest.main()
