import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = REPO_ROOT / "workspace" / "memory"
if str(MEMORY_DIR) not in sys.path:
    sys.path.insert(0, str(MEMORY_DIR))

from pause_check import _clamp, _count_pattern, _enabled, pause_check  # noqa: E402


class TestPauseCheck(unittest.TestCase):
    def test_pause_check_disabled_by_default(self):
        old = os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
        try:
            out = pause_check("ok", "Great question. Let's dive in with some broad context.", context={"test_mode": True})
            self.assertFalse(out["enabled"])
            self.assertEqual(out["decision"], "proceed")
        finally:
            if old is not None:
                os.environ["OPENCLAW_PAUSE_CHECK"] = old

    def test_pause_check_silences_verbose_filler_when_enabled(self):
        os.environ["OPENCLAW_PAUSE_CHECK"] = "1"
        try:
            draft = (
                "Great question. Let's dive in. Generally speaking, it depends and there are many things to consider. "
                "In summary, this is broad and not specific. " * 4
            )
            out = pause_check("ok", draft, context={"test_mode": True})
            self.assertTrue(out["enabled"])
            self.assertEqual(out["decision"], "silence")
            self.assertGreaterEqual(out["signals"]["fills_space"], 0.45)
        finally:
            os.environ.pop("OPENCLAW_PAUSE_CHECK", None)

    def test_pause_check_proceeds_on_concrete_draft(self):
        os.environ["OPENCLAW_PAUSE_CHECK"] = "1"
        try:
            draft = "Run: python3 -m pytest tests_unittest/test_pause_check.py and inspect workspace/scripts/team_chat_adapters.py"
            out = pause_check("help", draft, context={"test_mode": True})
            self.assertTrue(out["enabled"])
            self.assertEqual(out["decision"], "proceed")
            self.assertGreater(out["signals"]["value_add"], 0.3)
        finally:
            os.environ.pop("OPENCLAW_PAUSE_CHECK", None)


# ---------------------------------------------------------------------------
# _clamp
# ---------------------------------------------------------------------------

class TestClamp(unittest.TestCase):
    """Tests for _clamp() — round-and-clip to [0, 1]."""

    def test_zero_stays_zero(self):
        self.assertAlmostEqual(_clamp(0.0), 0.0)

    def test_one_stays_one(self):
        self.assertAlmostEqual(_clamp(1.0), 1.0)

    def test_below_zero_clamped(self):
        self.assertAlmostEqual(_clamp(-5.0), 0.0)

    def test_above_one_clamped(self):
        self.assertAlmostEqual(_clamp(2.0), 1.0)

    def test_rounds_to_3_decimals(self):
        result = _clamp(0.12345)
        # 0.12345 rounded to 3 decimals = 0.123
        self.assertAlmostEqual(result, 0.123)

    def test_midpoint_unchanged(self):
        self.assertAlmostEqual(_clamp(0.5), 0.5)


# ---------------------------------------------------------------------------
# _count_pattern
# ---------------------------------------------------------------------------

class TestCountPattern(unittest.TestCase):
    """Tests for _count_pattern() — case-insensitive regex findall count."""

    def test_zero_matches(self):
        self.assertEqual(_count_pattern(r"\bpython\b", "no hits here"), 0)

    def test_one_match(self):
        self.assertEqual(_count_pattern(r"\bpython\b", "run python3 now"), 0)
        self.assertEqual(_count_pattern(r"\bpython\b", "run python now"), 1)

    def test_multiple_matches(self):
        self.assertEqual(_count_pattern(r"\bstep\b", "step one step two step"), 3)

    def test_case_insensitive(self):
        self.assertEqual(_count_pattern(r"\bPYTHON\b", "use Python here"), 1)

    def test_empty_text(self):
        self.assertEqual(_count_pattern(r"\bword\b", ""), 0)

    def test_returns_int(self):
        self.assertIsInstance(_count_pattern(r"\b\w+\b", "hello"), int)


# ---------------------------------------------------------------------------
# _enabled
# ---------------------------------------------------------------------------

class TestEnabled(unittest.TestCase):
    """Tests for _enabled() — checks context.enabled or env var."""

    def test_context_enabled_true(self):
        self.assertTrue(_enabled({"enabled": True}))

    def test_context_enabled_false(self):
        self.assertFalse(_enabled({"enabled": False}))

    def test_env_var_1_enables(self):
        old = os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
        try:
            os.environ["OPENCLAW_PAUSE_CHECK"] = "1"
            self.assertTrue(_enabled({}))
        finally:
            os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
            if old is not None:
                os.environ["OPENCLAW_PAUSE_CHECK"] = old

    def test_env_var_0_disables(self):
        old = os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
        try:
            os.environ["OPENCLAW_PAUSE_CHECK"] = "0"
            self.assertFalse(_enabled({}))
        finally:
            os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
            if old is not None:
                os.environ["OPENCLAW_PAUSE_CHECK"] = old

    def test_context_takes_priority_over_env(self):
        old = os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
        try:
            os.environ["OPENCLAW_PAUSE_CHECK"] = "1"
            # context.enabled=False should override env=1
            self.assertFalse(_enabled({"enabled": False}))
        finally:
            os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
            if old is not None:
                os.environ["OPENCLAW_PAUSE_CHECK"] = old


# ---------------------------------------------------------------------------
# pause_check — additional signal and output structure tests
# ---------------------------------------------------------------------------

class TestPauseCheckOutputStructure(unittest.TestCase):
    """pause_check() output shape and signal properties."""

    def test_has_required_keys(self):
        out = pause_check("hello", "ok", context={"test_mode": True})
        for key in ("enabled", "decision", "rationale", "signals", "felt_sense", "mode"):
            self.assertIn(key, out)

    def test_signals_has_three_components(self):
        out = pause_check("hello", "ok", context={"test_mode": True})
        for sig in ("fills_space", "value_add", "silence_ok"):
            self.assertIn(sig, out["signals"])

    def test_signals_in_unit_interval(self):
        out = pause_check("sure", "maybe helpful", context={"test_mode": True, "enabled": True})
        for sig in ("fills_space", "value_add", "silence_ok"):
            v = out["signals"][sig]
            self.assertGreaterEqual(v, 0.0, msg=sig)
            self.assertLessEqual(v, 1.0, msg=sig)

    def test_empty_draft_proceeds_when_disabled(self):
        old = os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
        try:
            out = pause_check("hi", "", context={"test_mode": True})
            self.assertEqual(out["decision"], "proceed")
        finally:
            if old is not None:
                os.environ["OPENCLAW_PAUSE_CHECK"] = old

    def test_mode_passthrough(self):
        out = pause_check("hello", "ok", context={"test_mode": True}, mode="strict")
        self.assertEqual(out["mode"], "strict")

    def test_deterministic_same_inputs(self):
        args = ("what", "Great question. Let's dive in. " * 5)
        ctx = {"test_mode": True, "enabled": True}
        r1 = pause_check(*args, context=ctx)
        r2 = pause_check(*args, context=ctx)
        self.assertEqual(r1["signals"], r2["signals"])
        self.assertEqual(r1["decision"], r2["decision"])


if __name__ == "__main__":
    unittest.main()
