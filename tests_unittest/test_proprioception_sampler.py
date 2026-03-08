"""Tests for scripts.proprioception — ProprioceptiveSampler."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from proprioception import ProprioceptiveSampler


class TestProprioceptiveSamplerInit(unittest.TestCase):
    """Tests for ProprioceptiveSampler.__init__()."""

    def test_creates_instance(self):
        ps = ProprioceptiveSampler()
        self.assertIsNotNone(ps)

    def test_default_maxlen_200(self):
        ps = ProprioceptiveSampler()
        self.assertEqual(ps._buffer.maxlen, 200)

    def test_custom_maxlen_respected(self):
        ps = ProprioceptiveSampler(maxlen=50)
        self.assertEqual(ps._buffer.maxlen, 50)

    def test_minimum_maxlen_enforced(self):
        # maxlen below 10 is clamped to 10
        ps = ProprioceptiveSampler(maxlen=1)
        self.assertGreaterEqual(ps._buffer.maxlen, 10)

    def test_buffer_empty_on_init(self):
        ps = ProprioceptiveSampler()
        self.assertEqual(len(ps._buffer), 0)

    def test_breaker_open_providers_empty_on_init(self):
        ps = ProprioceptiveSampler()
        self.assertEqual(ps._breaker_open_providers, [])


class TestRecordDecision(unittest.TestCase):
    """Tests for ProprioceptiveSampler.record_decision()."""

    def setUp(self):
        self.ps = ProprioceptiveSampler()

    def test_increments_buffer(self):
        self.ps.record_decision(100.0)
        self.assertEqual(len(self.ps._buffer), 1)

    def test_duration_ms_stored(self):
        self.ps.record_decision(150.5)
        self.assertAlmostEqual(self.ps._buffer[-1]["duration_ms"], 150.5)

    def test_ok_defaults_to_true(self):
        self.ps.record_decision(100.0)
        self.assertTrue(self.ps._buffer[-1]["ok"])

    def test_ok_false_stored(self):
        self.ps.record_decision(100.0, ok=False)
        self.assertFalse(self.ps._buffer[-1]["ok"])

    def test_provider_stored(self):
        self.ps.record_decision(100.0, provider="openai")
        self.assertEqual(self.ps._buffer[-1]["provider"], "openai")

    def test_none_provider_stored_as_none(self):
        self.ps.record_decision(100.0, provider=None)
        self.assertIsNone(self.ps._buffer[-1]["provider"])

    def test_tokens_in_stored_as_int(self):
        self.ps.record_decision(100.0, tokens_in=512)
        self.assertEqual(self.ps._buffer[-1]["tokens_in"], 512)

    def test_non_int_tokens_in_stored_as_none(self):
        self.ps.record_decision(100.0, tokens_in="not_an_int")
        self.assertIsNone(self.ps._buffer[-1]["tokens_in"])

    def test_err_stored(self):
        self.ps.record_decision(100.0, ok=False, err="timeout")
        self.assertEqual(self.ps._buffer[-1]["err"], "timeout")

    def test_buffer_wraps_at_maxlen(self):
        ps = ProprioceptiveSampler(maxlen=10)
        for i in range(15):
            ps.record_decision(float(i))
        self.assertEqual(len(ps._buffer), 10)


class TestSetBreakerOpenProviders(unittest.TestCase):
    """Tests for set_breaker_open_providers()."""

    def setUp(self):
        self.ps = ProprioceptiveSampler()

    def test_sets_providers(self):
        self.ps.set_breaker_open_providers(["openai", "groq"])
        self.assertIn("openai", self.ps._breaker_open_providers)
        self.assertIn("groq", self.ps._breaker_open_providers)

    def test_sorted_alphabetically(self):
        self.ps.set_breaker_open_providers(["zzz", "aaa", "mmm"])
        self.assertEqual(
            self.ps._breaker_open_providers,
            sorted(self.ps._breaker_open_providers),
        )

    def test_deduplicates(self):
        self.ps.set_breaker_open_providers(["openai", "openai", "groq"])
        self.assertEqual(len(self.ps._breaker_open_providers), 2)

    def test_none_clears(self):
        self.ps.set_breaker_open_providers(["openai"])
        self.ps.set_breaker_open_providers(None)
        self.assertEqual(self.ps._breaker_open_providers, [])

    def test_empty_clears(self):
        self.ps.set_breaker_open_providers(["openai"])
        self.ps.set_breaker_open_providers([])
        self.assertEqual(self.ps._breaker_open_providers, [])

    def test_whitespace_only_excluded(self):
        self.ps.set_breaker_open_providers(["  ", "openai"])
        self.assertNotIn("  ", self.ps._breaker_open_providers)
        self.assertIn("openai", self.ps._breaker_open_providers)


class TestQuantile(unittest.TestCase):
    """Tests for ProprioceptiveSampler._quantile() — linear interpolation."""

    def setUp(self):
        self.ps = ProprioceptiveSampler()

    def test_empty_returns_zero(self):
        self.assertEqual(self.ps._quantile([], 0.5), 0.0)

    def test_single_value_any_quantile(self):
        self.assertEqual(self.ps._quantile([42.0], 0.0), 42.0)
        self.assertEqual(self.ps._quantile([42.0], 1.0), 42.0)

    def test_p50_of_even_list(self):
        result = self.ps._quantile([1.0, 2.0, 3.0, 4.0], 0.5)
        # p50 of [1,2,3,4] → linear interp at pos 1.5 → 2.5
        self.assertAlmostEqual(result, 2.5, places=5)

    def test_p0_returns_minimum(self):
        result = self.ps._quantile([3.0, 1.0, 2.0], 0.0)
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_p100_returns_maximum(self):
        result = self.ps._quantile([3.0, 1.0, 2.0], 1.0)
        self.assertAlmostEqual(result, 3.0, places=5)

    def test_q_clamped_to_0_1(self):
        # q > 1 clamped to 1
        result_high = self.ps._quantile([1.0, 2.0, 3.0], 5.0)
        result_max = self.ps._quantile([1.0, 2.0, 3.0], 1.0)
        self.assertAlmostEqual(result_high, result_max, places=5)


class TestSnapshot(unittest.TestCase):
    """Tests for ProprioceptiveSampler.snapshot()."""

    def setUp(self):
        self.ps = ProprioceptiveSampler()

    def test_empty_buffer_snapshot(self):
        snap = self.ps.snapshot()
        self.assertIsInstance(snap, dict)

    def test_snapshot_keys_present(self):
        snap = self.ps.snapshot()
        expected_keys = {
            "latency_ms_p50", "latency_ms_p95",
            "throughput_tokens_per_sec_p50", "throughput_tokens_per_sec_p95",
            "elapsed_ms_per_token_p50",
            "decisions_last_n", "error_rate",
            "breaker_open_providers", "timestamp_utc",
        }
        self.assertEqual(set(snap.keys()), expected_keys)

    def test_decisions_last_n_matches_buffer(self):
        for _ in range(5):
            self.ps.record_decision(100.0)
        snap = self.ps.snapshot()
        self.assertEqual(snap["decisions_last_n"], 5)

    def test_error_rate_zero_when_all_ok(self):
        for _ in range(10):
            self.ps.record_decision(100.0, ok=True)
        snap = self.ps.snapshot()
        self.assertAlmostEqual(snap["error_rate"], 0.0)

    def test_error_rate_100_percent(self):
        for _ in range(4):
            self.ps.record_decision(100.0, ok=False)
        snap = self.ps.snapshot()
        self.assertAlmostEqual(snap["error_rate"], 1.0)

    def test_latency_p50_computed(self):
        for ms in [100.0, 200.0, 300.0]:
            self.ps.record_decision(ms)
        snap = self.ps.snapshot()
        self.assertGreater(snap["latency_ms_p50"], 0.0)

    def test_timestamp_utc_ends_with_z(self):
        snap = self.ps.snapshot()
        self.assertTrue(snap["timestamp_utc"].endswith("Z"))

    def test_breaker_open_providers_in_snapshot(self):
        self.ps.set_breaker_open_providers(["openai"])
        snap = self.ps.snapshot()
        self.assertIn("openai", snap["breaker_open_providers"])

    def test_throughput_computed_when_tokens_provided(self):
        self.ps.record_decision(1000.0, tokens_in=100, tokens_out=50)
        snap = self.ps.snapshot()
        # 150 tokens in 1.0s = 150 tok/s
        self.assertGreater(snap["throughput_tokens_per_sec_p50"], 0.0)

    def test_empty_buffer_error_rate_zero(self):
        snap = self.ps.snapshot()
        self.assertAlmostEqual(snap["error_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
