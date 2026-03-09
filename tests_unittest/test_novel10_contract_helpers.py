"""Tests for workspace/tacti/novel10_contract.py.

Pure data constants and one pure function.

Covers:
- EXPECTED_EVENTS — dict structure and keys
- FEATURE_FLAGS — dict keys and default values
- required_for_fixture() — excludes/includes trail_heatmap based on include_ui + source-ui path
"""
import tempfile
import unittest
from pathlib import Path

from workspace.tacti.novel10_contract import (
    EXPECTED_EVENTS,
    FEATURE_FLAGS,
    required_for_fixture,
)


# ---------------------------------------------------------------------------
# EXPECTED_EVENTS
# ---------------------------------------------------------------------------


class TestExpectedEvents(unittest.TestCase):
    """Tests for EXPECTED_EVENTS — dict of feature → event type list."""

    def test_is_dict(self):
        self.assertIsInstance(EXPECTED_EVENTS, dict)

    def test_has_arousal_key(self):
        self.assertIn("arousal", EXPECTED_EVENTS)

    def test_has_expression_key(self):
        self.assertIn("expression", EXPECTED_EVENTS)

    def test_has_temporal_watchdog_key(self):
        self.assertIn("temporal_watchdog", EXPECTED_EVENTS)

    def test_has_dream_consolidation_key(self):
        self.assertIn("dream_consolidation", EXPECTED_EVENTS)

    def test_has_semantic_immune_key(self):
        self.assertIn("semantic_immune", EXPECTED_EVENTS)

    def test_has_stigmergy_key(self):
        self.assertIn("stigmergy", EXPECTED_EVENTS)

    def test_has_prefetch_key(self):
        self.assertIn("prefetch", EXPECTED_EVENTS)

    def test_has_mirror_key(self):
        self.assertIn("mirror", EXPECTED_EVENTS)

    def test_has_valence_key(self):
        self.assertIn("valence", EXPECTED_EVENTS)

    def test_has_trail_heatmap_key(self):
        self.assertIn("trail_heatmap", EXPECTED_EVENTS)

    def test_all_values_are_lists(self):
        for key, val in EXPECTED_EVENTS.items():
            self.assertIsInstance(val, list, f"EXPECTED_EVENTS[{key!r}] is not a list")

    def test_all_event_types_are_strings(self):
        for key, val in EXPECTED_EVENTS.items():
            for ev in val:
                self.assertIsInstance(ev, str, f"event type in {key!r} is not a string")

    def test_arousal_event_type(self):
        self.assertIn("tacti_cr.arousal_multiplier", EXPECTED_EVENTS["arousal"])

    def test_mirror_event_type(self):
        self.assertIn("tacti_cr.mirror.updated", EXPECTED_EVENTS["mirror"])


# ---------------------------------------------------------------------------
# FEATURE_FLAGS
# ---------------------------------------------------------------------------


class TestFeatureFlags(unittest.TestCase):
    """Tests for FEATURE_FLAGS — dict of env-var → default string value."""

    def test_is_dict(self):
        self.assertIsInstance(FEATURE_FLAGS, dict)

    def test_tacti_cr_enable_default_off(self):
        self.assertEqual(FEATURE_FLAGS["TACTI_CR_ENABLE"], "0")

    def test_tacti_cr_arousal_osc_default_off(self):
        self.assertEqual(FEATURE_FLAGS["TACTI_CR_AROUSAL_OSC"], "0")

    def test_tacti_cr_dream_default_off(self):
        self.assertEqual(FEATURE_FLAGS["TACTI_CR_DREAM_CONSOLIDATION"], "0")

    def test_tacti_cr_semantic_immune_default_off(self):
        self.assertEqual(FEATURE_FLAGS["TACTI_CR_SEMANTIC_IMMUNE"], "0")

    def test_tacti_cr_stigmergy_default_off(self):
        self.assertEqual(FEATURE_FLAGS["TACTI_CR_STIGMERGY"], "0")

    def test_tacti_cr_expression_router_default_off(self):
        self.assertEqual(FEATURE_FLAGS["TACTI_CR_EXPRESSION_ROUTER"], "0")

    def test_tacti_cr_prefetch_default_off(self):
        self.assertEqual(FEATURE_FLAGS["TACTI_CR_PREFETCH"], "0")

    def test_tacti_cr_mirror_default_off(self):
        self.assertEqual(FEATURE_FLAGS["TACTI_CR_MIRROR"], "0")

    def test_tacti_cr_valence_default_off(self):
        self.assertEqual(FEATURE_FLAGS["TACTI_CR_VALENCE"], "0")

    def test_tacti_cr_temporal_watchdog_default_off(self):
        self.assertEqual(FEATURE_FLAGS["TACTI_CR_TEMPORAL_WATCHDOG"], "0")

    def test_source_ui_heatmap_default_off(self):
        self.assertEqual(FEATURE_FLAGS["SOURCE_UI_HEATMAP"], "0")

    def test_all_values_are_strings(self):
        for k, v in FEATURE_FLAGS.items():
            self.assertIsInstance(v, str, f"FEATURE_FLAGS[{k!r}] is not a string")

    def test_all_values_are_zero(self):
        # All defaults are "0"
        for k, v in FEATURE_FLAGS.items():
            self.assertEqual(v, "0", f"FEATURE_FLAGS[{k!r}] is not '0'")


# ---------------------------------------------------------------------------
# required_for_fixture
# ---------------------------------------------------------------------------


class TestRequiredForFixture(unittest.TestCase):
    """Tests for required_for_fixture() — conditional event contract."""

    def test_returns_dict(self):
        self.assertIsInstance(required_for_fixture(), dict)

    def test_excludes_trail_heatmap_by_default(self):
        result = required_for_fixture()
        self.assertNotIn("trail_heatmap", result)

    def test_excludes_trail_heatmap_with_include_ui_false(self):
        result = required_for_fixture(include_ui=False)
        self.assertNotIn("trail_heatmap", result)

    def test_includes_all_other_features(self):
        result = required_for_fixture()
        expected_keys = {k for k in EXPECTED_EVENTS if k != "trail_heatmap"}
        self.assertTrue(expected_keys.issubset(result.keys()))

    def test_values_are_lists(self):
        result = required_for_fixture()
        for key, val in result.items():
            self.assertIsInstance(val, list)

    def test_values_are_copies_not_references(self):
        # Modifying returned dict should not affect EXPECTED_EVENTS
        result = required_for_fixture()
        result["arousal"].append("injected_event")
        self.assertNotIn("injected_event", EXPECTED_EVENTS["arousal"])

    def test_include_ui_true_without_source_ui_dir_excludes_trail_heatmap(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No source-ui directory created
            root = Path(tmp)
            (root / "workspace").mkdir()
            result = required_for_fixture(repo_root=root, include_ui=True)
            self.assertNotIn("trail_heatmap", result)

    def test_include_ui_true_with_source_ui_dir_includes_trail_heatmap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workspace" / "source-ui").mkdir(parents=True)
            result = required_for_fixture(repo_root=root, include_ui=True)
            self.assertIn("trail_heatmap", result)
            self.assertEqual(result["trail_heatmap"], EXPECTED_EVENTS["trail_heatmap"])


if __name__ == "__main__":
    unittest.main()
