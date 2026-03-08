"""Tests for store.probe_set — check_migration_safe, PROBE_SET structure."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_DIR = REPO_ROOT / "workspace" / "store"
if str(STORE_DIR) not in sys.path:
    sys.path.insert(0, str(STORE_DIR))

from probe_set import check_migration_safe, DEFAULT_MAX_DRIFT, PROBE_SET


class TestCheckMigrationSafe(unittest.TestCase):
    """Tests for check_migration_safe() — XCIII migration gate."""

    def _make_delta(self, drift_fraction=0.0, total=5, regressions=None):
        return {
            "drift_fraction": drift_fraction,
            "total_probes": total,
            "regressions": regressions or [],
        }

    def test_zero_drift_is_safe(self):
        delta = self._make_delta(drift_fraction=0.0)
        self.assertTrue(check_migration_safe(delta))

    def test_at_threshold_is_safe(self):
        # drift_fraction == max_drift → safe (≤ not <)
        delta = self._make_delta(drift_fraction=DEFAULT_MAX_DRIFT)
        self.assertTrue(check_migration_safe(delta))

    def test_above_threshold_blocks_migration(self):
        delta = self._make_delta(drift_fraction=DEFAULT_MAX_DRIFT + 0.01)
        self.assertFalse(check_migration_safe(delta))

    def test_high_drift_blocked(self):
        delta = self._make_delta(drift_fraction=1.0)
        self.assertFalse(check_migration_safe(delta))

    def test_custom_max_drift_respected(self):
        delta = self._make_delta(drift_fraction=0.2)
        self.assertTrue(check_migration_safe(delta, max_drift=0.25))
        self.assertFalse(check_migration_safe(delta, max_drift=0.1))

    def test_returns_bool(self):
        delta = self._make_delta(drift_fraction=0.0)
        result = check_migration_safe(delta)
        self.assertIsInstance(result, bool)


class TestProbeSet(unittest.TestCase):
    """Tests for PROBE_SET — fixed probe corpus structure."""

    def test_is_list(self):
        self.assertIsInstance(PROBE_SET, list)

    def test_non_empty(self):
        self.assertGreater(len(PROBE_SET), 0)

    def test_each_probe_is_three_tuple(self):
        for probe in PROBE_SET:
            self.assertEqual(len(probe), 3, f"Expected 3-tuple: {probe!r}")

    def test_query_is_string(self):
        for query, _, _ in PROBE_SET:
            self.assertIsInstance(query, str)
            self.assertGreater(len(query), 0)

    def test_expected_sections_is_list(self):
        for _, expected, _ in PROBE_SET:
            self.assertIsInstance(expected, list)

    def test_expected_sections_are_ints(self):
        for _, expected, _ in PROBE_SET:
            for n in expected:
                self.assertIsInstance(n, int)

    def test_description_is_string(self):
        for _, _, desc in PROBE_SET:
            self.assertIsInstance(desc, str)
            self.assertGreater(len(desc), 0)

    def test_inv001_probe_present(self):
        queries = [q for q, _, _ in PROBE_SET]
        self.assertTrue(any("INV-001" in q or "reservoir" in q.lower() for q in queries))

    def test_inv004_probe_present(self):
        queries = [q for q, _, _ in PROBE_SET]
        self.assertTrue(any("commit gate" in q.lower() or "INV-004" in q for q in queries))


class TestDefaultMaxDrift(unittest.TestCase):
    """Tests for DEFAULT_MAX_DRIFT constant."""

    def test_is_float(self):
        self.assertIsInstance(DEFAULT_MAX_DRIFT, float)

    def test_between_zero_and_one(self):
        self.assertGreater(DEFAULT_MAX_DRIFT, 0.0)
        self.assertLess(DEFAULT_MAX_DRIFT, 1.0)


if __name__ == "__main__":
    unittest.main()
