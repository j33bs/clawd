"""Tests for pure helpers in workspace/knowledge_base/embeddings/driver_mlx.py.

Covers:
- _backend_mode() — reads OPENCLAW_KB_EMBEDDINGS_BACKEND env var
- _effective_backend_mode() — downgrades to mock when mlx_embeddings is unavailable
- _mock_embed(text, dim) — deterministic hash-based mock embedding
- _normalize_rows(matrix) — L2-normalizes rows of a numpy matrix
"""
import importlib.util as _ilu
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "knowledge_base" / "embeddings" / "driver_mlx.py"

_spec = _ilu.spec_from_file_location("driver_mlx_real", str(MODULE_PATH))
drv = _ilu.module_from_spec(_spec)
sys.modules["driver_mlx_real"] = drv
_spec.loader.exec_module(drv)

_backend_mode = drv._backend_mode
_effective_backend_mode = drv._effective_backend_mode
_kb_mlx_venv_root = drv._kb_mlx_venv_root
_mock_embed = drv._mock_embed
_normalize_rows = drv._normalize_rows
_coerce_matrix = drv._coerce_matrix

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False


# ---------------------------------------------------------------------------
# _backend_mode
# ---------------------------------------------------------------------------


class TestBackendMode(unittest.TestCase):
    """Tests for _backend_mode() — reads env var, strips and lowercases."""

    def test_default_is_mlx(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENCLAW_KB_EMBEDDINGS_BACKEND", None)
            self.assertEqual(_backend_mode(), "mlx")

    def test_env_var_override(self):
        with patch.dict(os.environ, {"OPENCLAW_KB_EMBEDDINGS_BACKEND": "mock"}):
            self.assertEqual(_backend_mode(), "mock")

    def test_strips_whitespace(self):
        with patch.dict(os.environ, {"OPENCLAW_KB_EMBEDDINGS_BACKEND": "  mock  "}):
            self.assertEqual(_backend_mode(), "mock")

    def test_lowercases_value(self):
        with patch.dict(os.environ, {"OPENCLAW_KB_EMBEDDINGS_BACKEND": "MLX"}):
            self.assertEqual(_backend_mode(), "mlx")

    def test_returns_string(self):
        result = _backend_mode()
        self.assertIsInstance(result, str)


class TestKbMlxVenvRoot(unittest.TestCase):
    def test_default_path(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENCLAW_KB_MLX_VENV", None)
            self.assertTrue(str(_kb_mlx_venv_root()).endswith("workspace/runtime/embeddings/.venv_kb_mlx"))

    def test_env_override(self):
        with patch.dict(os.environ, {"OPENCLAW_KB_MLX_VENV": "/tmp/kb-mlx"}):
            self.assertEqual(_kb_mlx_venv_root(), Path("/tmp/kb-mlx").resolve())


class TestEffectiveBackendMode(unittest.TestCase):
    def test_defaults_to_mock_when_mlx_embeddings_missing(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENCLAW_KB_EMBEDDINGS_BACKEND", None)
            with patch.object(drv, "_mlx_embeddings_available", return_value=False):
                self.assertEqual(_effective_backend_mode(), "mock")

    def test_keeps_mlx_when_package_available(self):
        with patch.dict(os.environ, {"OPENCLAW_KB_EMBEDDINGS_BACKEND": "mlx"}, clear=False):
            with patch.object(drv, "_mlx_embeddings_available", return_value=True):
                self.assertEqual(_effective_backend_mode(), "mlx")

    def test_respects_explicit_non_mlx_backend(self):
        with patch.dict(os.environ, {"OPENCLAW_KB_EMBEDDINGS_BACKEND": "mock"}, clear=False):
            with patch.object(drv, "_mlx_embeddings_available", return_value=True):
                self.assertEqual(_effective_backend_mode(), "mock")


class TestRunMlxEmbed(unittest.TestCase):
    def test_uses_generate_for_tuple_backend(self):
        fake_module = type("FakeModule", (), {"generate": lambda self, model, tokenizer, texts: [[1.0, 2.0]]})()
        with patch.object(drv.importlib, "import_module", return_value=fake_module):
            result = drv._run_mlx_embed(("model", "tokenizer"), ["hello"])
        self.assertEqual(result, [[1.0, 2.0]])


# ---------------------------------------------------------------------------
# _mock_embed
# ---------------------------------------------------------------------------


class TestMockEmbed(unittest.TestCase):
    """Tests for _mock_embed(text, dim) — deterministic hash-based embedding."""

    def test_returns_list(self):
        result = _mock_embed("hello", 4)
        self.assertIsInstance(result, list)

    def test_length_equals_dim(self):
        for dim in (4, 16, 64, 384):
            result = _mock_embed("test", dim)
            self.assertEqual(len(result), dim, f"dim={dim}")

    def test_elements_are_floats(self):
        result = _mock_embed("word", 8)
        for val in result:
            self.assertIsInstance(val, float)

    def test_empty_string_returns_zeros(self):
        result = _mock_embed("", 8)
        self.assertEqual(result, [0.0] * 8)

    def test_none_returns_zeros(self):
        result = _mock_embed(None, 8)
        self.assertEqual(result, [0.0] * 8)

    def test_deterministic_same_text(self):
        a = _mock_embed("hello world", 32)
        b = _mock_embed("hello world", 32)
        self.assertEqual(a, b)

    def test_different_texts_different_vectors(self):
        a = _mock_embed("hello", 32)
        b = _mock_embed("world", 32)
        self.assertNotEqual(a, b)

    def test_dim_one(self):
        result = _mock_embed("x", 1)
        self.assertEqual(len(result), 1)

    def test_whitespace_only_is_empty(self):
        # Only whitespace → no tokens → zeros
        result = _mock_embed("   ", 4)
        self.assertEqual(result, [0.0] * 4)


# ---------------------------------------------------------------------------
# _normalize_rows
# ---------------------------------------------------------------------------


@unittest.skipUnless(_NUMPY_AVAILABLE, "numpy not available")
class TestNormalizeRows(unittest.TestCase):
    """Tests for _normalize_rows(matrix) — L2-normalizes matrix rows."""

    def test_returns_ndarray(self):
        import numpy as np
        m = np.array([[3.0, 4.0]], dtype=np.float32)
        result = _normalize_rows(m)
        self.assertIsInstance(result, np.ndarray)

    def test_unit_vector_unchanged(self):
        import numpy as np
        m = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
        result = _normalize_rows(m)
        np.testing.assert_allclose(result[0], [1.0, 0.0, 0.0], atol=1e-6)

    def test_3_4_vector_normalized(self):
        import numpy as np
        m = np.array([[3.0, 4.0]], dtype=np.float32)
        result = _normalize_rows(m)
        norm = np.linalg.norm(result[0])
        self.assertAlmostEqual(float(norm), 1.0, places=5)

    def test_zero_vector_unchanged(self):
        import numpy as np
        m = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
        result = _normalize_rows(m)
        # Zero vector: norm set to 1.0, so 0/1 = 0 — no NaN
        np.testing.assert_allclose(result[0], [0.0, 0.0, 0.0], atol=1e-6)

    def test_multiple_rows_all_unit_norm(self):
        import numpy as np
        m = np.array([
            [3.0, 4.0],
            [1.0, 0.0],
            [0.0, 2.0],
        ], dtype=np.float32)
        result = _normalize_rows(m)
        for i in range(result.shape[0]):
            norm = float(np.linalg.norm(result[i]))
            self.assertAlmostEqual(norm, 1.0, places=5, msg=f"row {i}")

    def test_shape_preserved(self):
        import numpy as np
        m = np.ones((5, 10), dtype=np.float32)
        result = _normalize_rows(m)
        self.assertEqual(result.shape, (5, 10))

    def test_no_nan_in_output(self):
        import numpy as np
        m = np.array([[0.0, 0.0], [1.0, 2.0]], dtype=np.float32)
        result = _normalize_rows(m)
        self.assertFalse(np.any(np.isnan(result)))

    def test_negative_values_normalized(self):
        import numpy as np
        m = np.array([[-3.0, -4.0]], dtype=np.float32)
        result = _normalize_rows(m)
        norm = float(np.linalg.norm(result[0]))
        self.assertAlmostEqual(norm, 1.0, places=5)


@unittest.skipUnless(_NUMPY_AVAILABLE, "numpy not available")
class TestCoerceMatrix(unittest.TestCase):
    def test_uses_pooler_output_when_present(self):
        import numpy as np

        class FakeOutput:
            pooler_output = np.array([[1.0, 2.0]], dtype=np.float32)

        result = _coerce_matrix(FakeOutput(), expected_rows=1)
        np.testing.assert_allclose(result, [[1.0, 2.0]], atol=1e-6)

    def test_mean_pools_token_level_text_embeds(self):
        import numpy as np

        class FakeOutput:
            text_embeds = np.array(
                [
                    [[1.0, 3.0], [3.0, 5.0]],
                    [[2.0, 4.0], [6.0, 8.0]],
                ],
                dtype=np.float32,
            )

        result = _coerce_matrix(FakeOutput(), expected_rows=2)
        np.testing.assert_allclose(result, [[2.0, 4.0], [4.0, 6.0]], atol=1e-6)


if __name__ == "__main__":
    unittest.main()
