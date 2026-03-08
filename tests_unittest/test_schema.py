"""Tests for store.schema — CorrespondenceSection, TRUST_EPOCH_VALUES, EXTERNAL_CALLERS."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_DIR = REPO_ROOT / "workspace" / "store"
if str(STORE_DIR) not in sys.path:
    sys.path.insert(0, str(STORE_DIR))

from schema import (
    CorrespondenceSection,
    TRUST_EPOCH_VALUES,
    EXTERNAL_CALLERS,
    EXEC_TAG_DARK_THRESHOLD,
    EXEC_DARK_FIELDS,
    DEFAULT_RETRO_DARK,
    TRUST_EPOCH_DEFAULT,
)


class TestCorrespondenceSectionDefaults(unittest.TestCase):
    """Tests for CorrespondenceSection default field values."""

    def _make(self, **kwargs) -> CorrespondenceSection:
        defaults = {"canonical_section_number": 1, "section_number_filed": "I"}
        defaults.update(kwargs)
        return CorrespondenceSection(**defaults)

    def test_authors_defaults_to_empty_list(self):
        cs = self._make()
        self.assertEqual(cs.authors, [])

    def test_exec_tags_defaults_to_empty_list(self):
        cs = self._make()
        self.assertEqual(cs.exec_tags, [])

    def test_status_tags_defaults_to_empty_list(self):
        cs = self._make()
        self.assertEqual(cs.status_tags, [])

    def test_embedding_defaults_to_empty_list(self):
        cs = self._make()
        self.assertEqual(cs.embedding, [])

    def test_retro_dark_fields_defaults_to_empty_list(self):
        cs = self._make()
        self.assertEqual(cs.retro_dark_fields, [])

    def test_collision_defaults_to_false(self):
        cs = self._make()
        self.assertFalse(cs.collision)

    def test_is_external_caller_defaults_to_false(self):
        cs = self._make()
        self.assertFalse(cs.is_external_caller)

    def test_trust_epoch_defaults_to_empty_string(self):
        cs = self._make()
        self.assertEqual(cs.trust_epoch, "")
        self.assertEqual(cs.trust_epoch, TRUST_EPOCH_DEFAULT)

    def test_response_to_defaults_to_none(self):
        cs = self._make()
        self.assertIsNone(cs.response_to)

    def test_knowledge_refs_defaults_to_none(self):
        cs = self._make()
        self.assertIsNone(cs.knowledge_refs)

    def test_embedding_version_defaults_to_one(self):
        cs = self._make()
        self.assertEqual(cs.embedding_version, 1)

    def test_title_defaults_to_empty_string(self):
        cs = self._make()
        self.assertEqual(cs.title, "")

    def test_body_defaults_to_empty_string(self):
        cs = self._make()
        self.assertEqual(cs.body, "")


class TestCorrespondenceSectionConstruction(unittest.TestCase):
    """Tests for CorrespondenceSection field assignment."""

    def test_canonical_section_number_stored(self):
        cs = CorrespondenceSection(canonical_section_number=42, section_number_filed="XLII")
        self.assertEqual(cs.canonical_section_number, 42)

    def test_section_number_filed_stored(self):
        cs = CorrespondenceSection(canonical_section_number=42, section_number_filed="XLII")
        self.assertEqual(cs.section_number_filed, "XLII")

    def test_authors_stored(self):
        cs = CorrespondenceSection(
            canonical_section_number=1, section_number_filed="I",
            authors=["Claude Code", "c_lawd"]
        )
        self.assertIn("Claude Code", cs.authors)
        self.assertIn("c_lawd", cs.authors)

    def test_trust_epoch_stored(self):
        cs = CorrespondenceSection(
            canonical_section_number=1, section_number_filed="I",
            trust_epoch="stable"
        )
        self.assertEqual(cs.trust_epoch, "stable")

    def test_authors_are_independent_across_instances(self):
        # Field factory — not shared mutable default
        cs1 = CorrespondenceSection(canonical_section_number=1, section_number_filed="I")
        cs2 = CorrespondenceSection(canonical_section_number=2, section_number_filed="II")
        cs1.authors.append("Claude Code")
        self.assertEqual(cs2.authors, [])


class TestIsRetroDark(unittest.TestCase):
    """Tests for CorrespondenceSection.is_retro_dark()."""

    def _make_with_dark(self, fields: list) -> CorrespondenceSection:
        return CorrespondenceSection(
            canonical_section_number=10, section_number_filed="X",
            retro_dark_fields=fields
        )

    def test_field_in_list_returns_true(self):
        cs = self._make_with_dark(["exec_tags"])
        self.assertTrue(cs.is_retro_dark("exec_tags"))

    def test_field_not_in_list_returns_false(self):
        cs = self._make_with_dark(["exec_tags"])
        self.assertFalse(cs.is_retro_dark("title"))

    def test_empty_dark_fields_all_false(self):
        cs = self._make_with_dark([])
        self.assertFalse(cs.is_retro_dark("exec_tags"))
        self.assertFalse(cs.is_retro_dark("response_to"))

    def test_multiple_dark_fields(self):
        cs = self._make_with_dark(["exec_tags", "response_to", "knowledge_refs"])
        self.assertTrue(cs.is_retro_dark("exec_tags"))
        self.assertTrue(cs.is_retro_dark("response_to"))
        self.assertTrue(cs.is_retro_dark("knowledge_refs"))


class TestRetroDarkForNumber(unittest.TestCase):
    """Tests for CorrespondenceSection.retro_dark_for_number()."""

    def test_section_at_threshold_is_dark(self):
        # n <= EXEC_TAG_DARK_THRESHOLD → full EXEC_DARK_FIELDS
        result = CorrespondenceSection.retro_dark_for_number(EXEC_TAG_DARK_THRESHOLD)
        self.assertEqual(result, EXEC_DARK_FIELDS)

    def test_section_below_threshold_is_dark(self):
        result = CorrespondenceSection.retro_dark_for_number(1)
        self.assertEqual(result, EXEC_DARK_FIELDS)

    def test_section_above_threshold_is_partial(self):
        result = CorrespondenceSection.retro_dark_for_number(EXEC_TAG_DARK_THRESHOLD + 1)
        self.assertEqual(result, DEFAULT_RETRO_DARK)

    def test_modern_section_is_partial_dark(self):
        result = CorrespondenceSection.retro_dark_for_number(158)
        self.assertEqual(result, DEFAULT_RETRO_DARK)

    def test_exec_dark_fields_contains_exec_tags(self):
        self.assertIn("exec_tags", EXEC_DARK_FIELDS)

    def test_exec_dark_fields_contains_exec_decisions(self):
        self.assertIn("exec_decisions", EXEC_DARK_FIELDS)

    def test_exec_dark_fields_superset_of_default_retro_dark(self):
        for field in DEFAULT_RETRO_DARK:
            self.assertIn(field, EXEC_DARK_FIELDS)


class TestTrustEpochValues(unittest.TestCase):
    """Tests for TRUST_EPOCH_VALUES constant."""

    def test_is_set(self):
        self.assertIsInstance(TRUST_EPOCH_VALUES, set)

    def test_building_present(self):
        self.assertIn("building", TRUST_EPOCH_VALUES)

    def test_stable_present(self):
        self.assertIn("stable", TRUST_EPOCH_VALUES)

    def test_degraded_present(self):
        self.assertIn("degraded", TRUST_EPOCH_VALUES)

    def test_recovering_present(self):
        self.assertIn("recovering", TRUST_EPOCH_VALUES)

    def test_non_empty(self):
        self.assertGreater(len(TRUST_EPOCH_VALUES), 0)

    def test_all_lowercase(self):
        for v in TRUST_EPOCH_VALUES:
            self.assertEqual(v, v.lower())


class TestExternalCallers(unittest.TestCase):
    """Tests for EXTERNAL_CALLERS set."""

    def test_is_set(self):
        self.assertIsInstance(EXTERNAL_CALLERS, set)

    def test_chatgpt_present(self):
        self.assertIn("chatgpt", EXTERNAL_CALLERS)

    def test_grok_present(self):
        self.assertIn("grok", EXTERNAL_CALLERS)

    def test_gemini_present(self):
        self.assertIn("gemini", EXTERNAL_CALLERS)

    def test_claude_ext_present(self):
        self.assertIn("claude (ext)", EXTERNAL_CALLERS)

    def test_all_lowercase(self):
        for c in EXTERNAL_CALLERS:
            self.assertEqual(c, c.lower())

    def test_non_empty(self):
        self.assertGreater(len(EXTERNAL_CALLERS), 0)


if __name__ == "__main__":
    unittest.main()
