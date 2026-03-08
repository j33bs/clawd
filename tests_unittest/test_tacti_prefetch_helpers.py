"""Tests for pure helpers in workspace/tacti/prefetch.py.

Requires stubs for tacti.config (get_int, is_enabled) and tacti.events (emit).
The predict_topics function is purely stdlib — no external deps.

Covers:
- predict_topics
- PrefetchCache._load_index
- PrefetchCache._save_index
- PrefetchCache.depth
- PrefetchCache.record_hit (pure logic, mocked emit)
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
TACTI_DIR = REPO_ROOT / "workspace" / "tacti"


# ---------------------------------------------------------------------------
# Set up tacti package + stub relative imports
# ---------------------------------------------------------------------------

def _ensure_tacti_pkg():
    if "tacti" not in sys.modules:
        pkg = types.ModuleType("tacti")
        pkg.__path__ = [str(TACTI_DIR)]
        pkg.__package__ = "tacti"
        sys.modules["tacti"] = pkg

def _ensure_tacti_config_stub():
    if "tacti.config" not in sys.modules:
        mod = types.ModuleType("tacti.config")
        sys.modules["tacti.config"] = mod
        setattr(sys.modules["tacti"], "config", mod)
    mod = sys.modules["tacti.config"]
    if not hasattr(mod, "get_int"):
        mod.get_int = lambda name, default, clamp=None: default
    if not hasattr(mod, "is_enabled"):
        mod.is_enabled = lambda feature_name: False

def _ensure_tacti_events_stub():
    if "tacti.events" not in sys.modules:
        mod = types.ModuleType("tacti.events")
        sys.modules["tacti.events"] = mod
        setattr(sys.modules["tacti"], "events", mod)
    mod = sys.modules["tacti.events"]
    if not hasattr(mod, "emit"):
        mod.emit = lambda *a, **kw: None


_ensure_tacti_pkg()
_ensure_tacti_config_stub()
_ensure_tacti_events_stub()

_spec = _ilu.spec_from_file_location(
    "tacti.prefetch",
    str(TACTI_DIR / "prefetch.py"),
)
pf = _ilu.module_from_spec(_spec)
pf.__package__ = "tacti"
sys.modules["tacti.prefetch"] = pf
_spec.loader.exec_module(pf)


# ---------------------------------------------------------------------------
# predict_topics
# ---------------------------------------------------------------------------

class TestPredictTopics(unittest.TestCase):
    """Tests for predict_topics() — token frequency analysis."""

    def test_returns_list(self):
        result = pf.predict_topics("hello world hello world")
        self.assertIsInstance(result, list)

    def test_top_k_limit(self):
        result = pf.predict_topics("a a b b c c d d e e", top_k=2)
        self.assertLessEqual(len(result), 2)

    def test_most_frequent_first(self):
        # "active" appears 3x, "inference" 1x
        result = pf.predict_topics("active active active inference", top_k=2)
        self.assertEqual(result[0], "active")

    def test_case_insensitive(self):
        result = pf.predict_topics("Hello HELLO hello world", top_k=1)
        self.assertEqual(result[0], "hello")

    def test_empty_string_returns_list(self):
        result = pf.predict_topics("", top_k=3)
        self.assertIsInstance(result, list)

    def test_last_n_windowing(self):
        # With last_n=1, only the last token counts
        stream = ("other " * 50) + "target"
        result = pf.predict_topics(stream, last_n=1, top_k=1)
        self.assertEqual(result[0], "target")

    def test_alphanumeric_tokens_only(self):
        result = pf.predict_topics("hello! world, foo-bar")
        # punctuation should not appear in tokens
        for tok in result:
            self.assertRegex(tok, r"^[a-z0-9_\-]+$")


# ---------------------------------------------------------------------------
# PrefetchCache._load_index
# ---------------------------------------------------------------------------

class TestPrefetchCacheLoadIndex(unittest.TestCase):
    """Tests for PrefetchCache._load_index() — reads or creates default index."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._cache = pf.PrefetchCache(repo_root=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_returns_defaults(self):
        idx = self._cache._load_index()
        self.assertIn("hits", idx)
        self.assertIn("misses", idx)
        self.assertIn("depth", idx)
        self.assertIn("lru", idx)

    def test_default_depth_is_3(self):
        idx = self._cache._load_index()
        self.assertEqual(idx["depth"], 3)

    def test_saves_and_loads_roundtrip(self):
        idx = self._cache._load_index()
        idx["hits"] = 42
        self._cache._save_index(idx)
        loaded = self._cache._load_index()
        self.assertEqual(loaded["hits"], 42)

    def test_invalid_json_returns_defaults(self):
        self._cache.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache.index_path.write_text("not json", encoding="utf-8")
        idx = self._cache._load_index()
        self.assertEqual(idx["depth"], 3)


# ---------------------------------------------------------------------------
# PrefetchCache.depth
# ---------------------------------------------------------------------------

class TestPrefetchCacheDepth(unittest.TestCase):
    """Tests for PrefetchCache.depth() — returns depth from index."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._cache = pf.PrefetchCache(repo_root=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_default_depth_is_3(self):
        self.assertEqual(self._cache.depth(), 3)

    def test_saved_depth_returned(self):
        idx = self._cache._load_index()
        idx["depth"] = 5
        self._cache._save_index(idx)
        self.assertEqual(self._cache.depth(), 5)

    def test_returns_int(self):
        self.assertIsInstance(self._cache.depth(), int)


# ---------------------------------------------------------------------------
# PrefetchCache.record_hit
# ---------------------------------------------------------------------------

class TestPrefetchCacheRecordHit(unittest.TestCase):
    """Tests for PrefetchCache.record_hit() — updates hit/miss counters."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._cache = pf.PrefetchCache(repo_root=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_hit_increments_hits(self):
        result = self._cache.record_hit(True)
        self.assertEqual(result["total"], 1)

    def test_miss_increments_misses(self):
        result = self._cache.record_hit(False)
        self.assertEqual(result["total"], 1)

    def test_hit_rate_calculation(self):
        self._cache.record_hit(True)
        result = self._cache.record_hit(True)
        self.assertAlmostEqual(result["hit_rate"], 1.0)

    def test_returns_dict(self):
        result = self._cache.record_hit(True)
        self.assertIsInstance(result, dict)
        self.assertIn("hit_rate", result)
        self.assertIn("depth", result)


if __name__ == "__main__":
    unittest.main()
