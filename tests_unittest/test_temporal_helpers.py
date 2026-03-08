"""Tests for pure helpers in workspace/tacti/temporal.py.

Stubs tacti.config (with DEFAULT_CONFIG), tacti.events, tacti.hivemind_bridge,
and tacti.temporal_watchdog to allow clean module load.

Covers:
- _coerce_float
- _normalize_distribution
- text_embedding_proxy
- surprise_score_proxy
- _surprise_gate_enabled
"""
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = REPO_ROOT / "workspace"


# ---------------------------------------------------------------------------
# Build tacti stubs (setdefault-safe; extend existing stubs if needed)
# ---------------------------------------------------------------------------

def _ensure_tacti_temporal_stubs():
    """Install tacti sub-module stubs needed to load temporal.py."""
    # --- tacti package ---
    if "tacti" not in sys.modules:
        pkg = types.ModuleType("tacti")
        pkg.__path__ = [str(WORKSPACE_DIR / "tacti")]
        sys.modules["tacti"] = pkg
    tacti_pkg = sys.modules["tacti"]

    # --- tacti.config (needs DEFAULT_CONFIG) ---
    if "tacti.config" not in sys.modules:
        cfg = types.ModuleType("tacti.config")
        sys.modules["tacti.config"] = cfg
        setattr(tacti_pkg, "config", cfg)
    cfg = sys.modules["tacti.config"]
    if not hasattr(cfg, "DEFAULT_CONFIG"):
        class _TC:
            default_decay_rate = 0.05
            retention_days = 90
        class _Cfg:
            temporal = _TC()
        cfg.DEFAULT_CONFIG = _Cfg()
    if not hasattr(cfg, "get_int"):
        cfg.get_int = lambda k, d, clamp=None: d
    if not hasattr(cfg, "get_float"):
        cfg.get_float = lambda k, d, clamp=None: d
    if not hasattr(cfg, "is_enabled"):
        cfg.is_enabled = lambda k: False

    # --- tacti.events ---
    sys.modules.setdefault("tacti.events", types.ModuleType("tacti.events"))
    ev = sys.modules["tacti.events"]
    if not hasattr(ev, "emit"):
        ev.emit = lambda *a, **kw: None
    setattr(tacti_pkg, "events", ev)

    # --- tacti.hivemind_bridge ---
    sys.modules.setdefault("tacti.hivemind_bridge", types.ModuleType("tacti.hivemind_bridge"))
    hb = sys.modules["tacti.hivemind_bridge"]
    if not hasattr(hb, "hivemind_query"):
        hb.hivemind_query = lambda *a, **kw: []
    if not hasattr(hb, "hivemind_store"):
        hb.hivemind_store = lambda *a, **kw: None
    setattr(tacti_pkg, "hivemind_bridge", hb)

    # --- tacti.temporal_watchdog ---
    sys.modules.setdefault("tacti.temporal_watchdog", types.ModuleType("tacti.temporal_watchdog"))
    tw = sys.modules["tacti.temporal_watchdog"]
    if not hasattr(tw, "temporal_reset_event"):
        tw.temporal_reset_event = lambda *a, **kw: None
    setattr(tacti_pkg, "temporal_watchdog", tw)


_ensure_tacti_temporal_stubs()

if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from tacti import temporal as tm  # noqa: E402


# ---------------------------------------------------------------------------
# _coerce_float
# ---------------------------------------------------------------------------

class TestCoerceFloat(unittest.TestCase):
    """Tests for _coerce_float() — coerce to float with fallback."""

    def test_valid_float(self):
        self.assertAlmostEqual(tm._coerce_float(3.14, 0.0), 3.14)

    def test_valid_string_float(self):
        self.assertAlmostEqual(tm._coerce_float("2.5", 0.0), 2.5)

    def test_none_returns_fallback(self):
        self.assertAlmostEqual(tm._coerce_float(None, 9.9), 9.9)

    def test_invalid_string_returns_fallback(self):
        self.assertAlmostEqual(tm._coerce_float("abc", 7.0), 7.0)

    def test_integer_coerced(self):
        self.assertAlmostEqual(tm._coerce_float(5, 0.0), 5.0)

    def test_returns_float(self):
        self.assertIsInstance(tm._coerce_float(1, 0.0), float)


# ---------------------------------------------------------------------------
# _normalize_distribution
# ---------------------------------------------------------------------------

class TestNormalizeDistribution(unittest.TestCase):
    """Tests for _normalize_distribution() — sum-1 positive distribution."""

    def test_empty_returns_singleton_one(self):
        result = tm._normalize_distribution([])
        self.assertEqual(result, [1.0])

    def test_sum_is_one(self):
        result = tm._normalize_distribution([1.0, 2.0, 3.0])
        self.assertAlmostEqual(sum(result), 1.0, places=10)

    def test_equal_weights_uniform(self):
        result = tm._normalize_distribution([1.0, 1.0])
        self.assertAlmostEqual(result[0], 0.5)
        self.assertAlmostEqual(result[1], 0.5)

    def test_all_zero_falls_back_to_uniform(self):
        result = tm._normalize_distribution([0.0, 0.0, 0.0])
        self.assertAlmostEqual(sum(result), 1.0, places=10)

    def test_preserves_length(self):
        result = tm._normalize_distribution([2.0, 3.0, 5.0])
        self.assertEqual(len(result), 3)

    def test_all_elements_positive(self):
        result = tm._normalize_distribution([1.0, 2.0, 0.5])
        for v in result:
            self.assertGreater(v, 0.0)


# ---------------------------------------------------------------------------
# text_embedding_proxy
# ---------------------------------------------------------------------------

class TestTextEmbeddingProxy(unittest.TestCase):
    """Tests for text_embedding_proxy() — hash-based dim embedding."""

    def test_returns_list(self):
        result = tm.text_embedding_proxy("hello world")
        self.assertIsInstance(result, list)

    def test_default_dim(self):
        result = tm.text_embedding_proxy("test text")
        self.assertEqual(len(result), 16)

    def test_custom_dim(self):
        result = tm.text_embedding_proxy("test", dim=32)
        self.assertEqual(len(result), 32)

    def test_sums_to_one(self):
        result = tm.text_embedding_proxy("some text here")
        self.assertAlmostEqual(sum(result), 1.0, places=10)

    def test_deterministic(self):
        a = tm.text_embedding_proxy("same input")
        b = tm.text_embedding_proxy("same input")
        self.assertEqual(a, b)

    def test_different_texts_differ(self):
        a = tm.text_embedding_proxy("apple pie")
        b = tm.text_embedding_proxy("banana bread")
        self.assertNotEqual(a, b)


# ---------------------------------------------------------------------------
# surprise_score_proxy
# ---------------------------------------------------------------------------

class TestSurpriseScoreProxy(unittest.TestCase):
    """Tests for surprise_score_proxy() — KL-divergence-based surprise."""

    def test_same_input_low_surprise(self):
        # Same string for p and q → very low KL divergence
        result = tm.surprise_score_proxy("hello world", "hello world")
        self.assertAlmostEqual(result, 0.0, places=5)

    def test_different_inputs_positive(self):
        result = tm.surprise_score_proxy("alpha beta gamma", "delta epsilon zeta")
        self.assertGreaterEqual(result, 0.0)

    def test_non_negative(self):
        result = tm.surprise_score_proxy("a b c", "x y z")
        self.assertGreaterEqual(result, 0.0)

    def test_returns_float(self):
        result = tm.surprise_score_proxy("foo", "bar")
        self.assertIsInstance(result, float)

    def test_list_inputs(self):
        p = [0.5, 0.3, 0.2]
        q = [0.2, 0.3, 0.5]
        result = tm.surprise_score_proxy(p, q)
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0.0)


# ---------------------------------------------------------------------------
# _surprise_gate_enabled
# ---------------------------------------------------------------------------

class TestSurpriseGateEnabled(unittest.TestCase):
    """Tests for _surprise_gate_enabled() — env flag check."""

    def test_default_disabled(self):
        env = {k: v for k, v in os.environ.items()
               if k not in {"OPENCLAW_TEMPORAL_SURPRISE_GATE", "OPENCLAW_SURPRISE_GATE"}}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(tm._surprise_gate_enabled())

    def test_primary_key_enables(self):
        with patch.dict(os.environ, {"OPENCLAW_TEMPORAL_SURPRISE_GATE": "1"}):
            self.assertTrue(tm._surprise_gate_enabled())

    def test_secondary_key_enables(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_TEMPORAL_SURPRISE_GATE"}
        env["OPENCLAW_SURPRISE_GATE"] = "true"
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(tm._surprise_gate_enabled())

    def test_zero_disables(self):
        with patch.dict(os.environ, {"OPENCLAW_TEMPORAL_SURPRISE_GATE": "0"}):
            self.assertFalse(tm._surprise_gate_enabled())

    def test_returns_bool(self):
        self.assertIsInstance(tm._surprise_gate_enabled(), bool)


if __name__ == "__main__":
    unittest.main()
