"""Tests for workspace/tacti/config.py pure helpers.

No external deps — config.py is stdlib-only. Loaded with a unique module name
to avoid colliding with the tacti.config stub installed by other test files.

Covers:
- _parse_bool
- get_float
- get_int
- get_time_zone
- is_enabled
"""
import importlib.util as _ilu
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

# Load config.py with a unique name so the tacti.config stub in sys.modules
# (installed by test_expression_helpers etc.) doesn't shadow it.
_spec = _ilu.spec_from_file_location(
    "tacti_config_real",
    str(REPO_ROOT / "workspace" / "tacti" / "config.py"),
)
cfg = _ilu.module_from_spec(_spec)
sys.modules["tacti_config_real"] = cfg  # dataclass needs module in sys.modules
_spec.loader.exec_module(cfg)


# ---------------------------------------------------------------------------
# _parse_bool
# ---------------------------------------------------------------------------

class TestParseBool(unittest.TestCase):
    """Tests for _parse_bool() — coerces arbitrary values to bool."""

    def test_true_bool(self):
        self.assertTrue(cfg._parse_bool(True))

    def test_false_bool(self):
        self.assertFalse(cfg._parse_bool(False))

    def test_string_one(self):
        self.assertTrue(cfg._parse_bool("1"))

    def test_string_true(self):
        self.assertTrue(cfg._parse_bool("true"))

    def test_string_yes(self):
        self.assertTrue(cfg._parse_bool("yes"))

    def test_string_on(self):
        self.assertTrue(cfg._parse_bool("on"))

    def test_string_enabled(self):
        self.assertTrue(cfg._parse_bool("enabled"))

    def test_string_zero_is_false(self):
        self.assertFalse(cfg._parse_bool("0"))

    def test_string_false_is_false(self):
        self.assertFalse(cfg._parse_bool("false"))

    def test_empty_string_is_false(self):
        self.assertFalse(cfg._parse_bool(""))

    def test_none_is_false(self):
        self.assertFalse(cfg._parse_bool(None))

    def test_case_insensitive(self):
        self.assertTrue(cfg._parse_bool("TRUE"))
        self.assertTrue(cfg._parse_bool("Yes"))
        self.assertTrue(cfg._parse_bool("ON"))

    def test_returns_bool(self):
        self.assertIsInstance(cfg._parse_bool("1"), bool)


# ---------------------------------------------------------------------------
# get_float
# ---------------------------------------------------------------------------

class TestGetFloat(unittest.TestCase):
    """Tests for get_float() — read float knob with optional clamping."""

    def test_default_used_without_env(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("TACTI_CR_")}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(cfg, "_policy_knobs", return_value={}):
                result = cfg.get_float("some_float", 0.5)
                self.assertAlmostEqual(result, 0.5)

    def test_env_override(self):
        with patch.dict(os.environ, {"TACTI_CR_MY_FLOAT": "0.75"}):
            result = cfg.get_float("my_float", 0.1)
            self.assertAlmostEqual(result, 0.75)

    def test_invalid_env_falls_back_to_default(self):
        with patch.dict(os.environ, {"TACTI_CR_MY_FLOAT": "not-a-float"}):
            result = cfg.get_float("my_float", 0.3)
            self.assertAlmostEqual(result, 0.3)

    def test_clamp_upper(self):
        with patch.dict(os.environ, {"TACTI_CR_MY_FLOAT": "5.0"}):
            result = cfg.get_float("my_float", 0.0, clamp=(0.0, 1.0))
            self.assertAlmostEqual(result, 1.0)

    def test_clamp_lower(self):
        with patch.dict(os.environ, {"TACTI_CR_MY_FLOAT": "-5.0"}):
            result = cfg.get_float("my_float", 0.0, clamp=(0.0, 1.0))
            self.assertAlmostEqual(result, 0.0)

    def test_no_clamp_no_truncation(self):
        with patch.dict(os.environ, {"TACTI_CR_MY_FLOAT": "99.9"}):
            result = cfg.get_float("my_float", 0.0)
            self.assertAlmostEqual(result, 99.9)

    def test_returns_float(self):
        with patch.object(cfg, "_policy_knobs", return_value={}):
            result = cfg.get_float("x", 1)
            self.assertIsInstance(result, float)


# ---------------------------------------------------------------------------
# get_int
# ---------------------------------------------------------------------------

class TestGetInt(unittest.TestCase):
    """Tests for get_int() — read int knob with optional clamping."""

    def test_default_used(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("TACTI_CR_")}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(cfg, "_policy_knobs", return_value={}):
                result = cfg.get_int("some_int", 42)
                self.assertEqual(result, 42)

    def test_env_override(self):
        with patch.dict(os.environ, {"TACTI_CR_MY_INT": "7"}):
            result = cfg.get_int("my_int", 0)
            self.assertEqual(result, 7)

    def test_invalid_env_falls_back(self):
        with patch.dict(os.environ, {"TACTI_CR_MY_INT": "bad"}):
            result = cfg.get_int("my_int", 99)
            self.assertEqual(result, 99)

    def test_clamp_upper(self):
        with patch.dict(os.environ, {"TACTI_CR_MY_INT": "1000"}):
            result = cfg.get_int("my_int", 0, clamp=(0, 100))
            self.assertEqual(result, 100)

    def test_clamp_lower(self):
        with patch.dict(os.environ, {"TACTI_CR_MY_INT": "-50"}):
            result = cfg.get_int("my_int", 0, clamp=(0, 100))
            self.assertEqual(result, 0)

    def test_returns_int(self):
        with patch.object(cfg, "_policy_knobs", return_value={}):
            result = cfg.get_int("x", 5)
            self.assertIsInstance(result, int)


# ---------------------------------------------------------------------------
# get_time_zone
# ---------------------------------------------------------------------------

class TestGetTimeZone(unittest.TestCase):
    """Tests for get_time_zone() — returns configured timezone string."""

    def test_default_returned_when_no_config(self):
        with patch.object(cfg, "_policy_knobs", return_value={}):
            env = {k: v for k, v in os.environ.items() if k != "TACTI_CR_TIME_ZONE"}
            with patch.dict(os.environ, env, clear=True):
                result = cfg.get_time_zone()
                self.assertEqual(result, "Australia/Brisbane")

    def test_env_override(self):
        with patch.dict(os.environ, {"TACTI_CR_TIME_ZONE": "America/New_York"}):
            result = cfg.get_time_zone()
            self.assertEqual(result, "America/New_York")

    def test_empty_env_uses_default(self):
        with patch.dict(os.environ, {"TACTI_CR_TIME_ZONE": ""}):
            with patch.object(cfg, "_policy_knobs", return_value={}):
                result = cfg.get_time_zone(default="UTC")
                self.assertEqual(result, "UTC")

    def test_returns_string(self):
        with patch.object(cfg, "_policy_knobs", return_value={}):
            result = cfg.get_time_zone()
            self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# is_enabled
# ---------------------------------------------------------------------------

class TestIsEnabled(unittest.TestCase):
    """Tests for is_enabled() — master gate + per-feature gate."""

    def test_master_off_returns_false(self):
        env = {k: v for k, v in os.environ.items() if k != "TACTI_CR_ENABLE"}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(cfg.is_enabled("arousal_osc"))

    def test_master_on_sub_feature_on(self):
        with patch.dict(os.environ, {
            "TACTI_CR_ENABLE": "1",
            "TACTI_CR_AROUSAL_OSC": "1",
        }):
            self.assertTrue(cfg.is_enabled("arousal_osc"))

    def test_master_on_sub_feature_off(self):
        env = {k: v for k, v in os.environ.items()}
        env["TACTI_CR_ENABLE"] = "1"
        env.pop("TACTI_CR_AROUSAL_OSC", None)
        with patch.dict(os.environ, env, clear=True):
            with patch.object(cfg, "_policy_knobs", return_value={}):
                self.assertFalse(cfg.is_enabled("arousal_osc"))

    def test_master_feature_itself_returns_true_when_enabled(self):
        with patch.dict(os.environ, {"TACTI_CR_ENABLE": "1"}):
            self.assertTrue(cfg.is_enabled("master"))

    def test_returns_bool(self):
        env = {k: v for k, v in os.environ.items() if k != "TACTI_CR_ENABLE"}
        with patch.dict(os.environ, env, clear=True):
            result = cfg.is_enabled("arousal_osc")
            self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
