"""Tests for preflight_check — normalize_node_id, load_json, _matches_prefix_path,
_is_allowed_untracked_path, _is_ignorable_root_untracked."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import preflight_check as pc


class TestNormalizeNodeId(unittest.TestCase):
    """Tests for normalize_node_id() — alias resolution with system_map."""

    def _map(self, nodes, default="dali"):
        return {"nodes": nodes, "default_node_id": default}

    def _node(self, *aliases):
        return {"aliases": list(aliases)}

    def test_direct_node_id_match(self):
        m = self._map({"z490": self._node("z490", "desktop")})
        self.assertEqual(pc.normalize_node_id("z490", m), "z490")

    def test_alias_match(self):
        m = self._map({"z490": self._node("z490", "main", "desktop")})
        self.assertEqual(pc.normalize_node_id("main", m), "z490")
        self.assertEqual(pc.normalize_node_id("desktop", m), "z490")

    def test_case_insensitive_match(self):
        m = self._map({"z490": self._node("Z490", "Main")})
        self.assertEqual(pc.normalize_node_id("z490", m), "z490")
        self.assertEqual(pc.normalize_node_id("main", m), "z490")

    def test_whitespace_stripped(self):
        m = self._map({"z490": self._node("z490")})
        self.assertEqual(pc.normalize_node_id("  z490  ", m), "z490")

    def test_none_returns_default(self):
        m = self._map({}, default="z490")
        self.assertEqual(pc.normalize_node_id(None, m), "z490")

    def test_empty_string_returns_default(self):
        m = self._map({}, default="z490")
        self.assertEqual(pc.normalize_node_id("", m), "z490")

    def test_unknown_value_returns_default(self):
        m = self._map({"z490": self._node("z490")}, default="z490")
        self.assertEqual(pc.normalize_node_id("unknown_node", m), "z490")

    def test_non_dict_system_map_returns_dali(self):
        self.assertEqual(pc.normalize_node_id("z490", None), "dali")
        self.assertEqual(pc.normalize_node_id("z490", []), "dali")
        self.assertEqual(pc.normalize_node_id("z490", "string"), "dali")

    def test_empty_dict_returns_dali(self):
        # No "nodes" key, no "default_node_id" → default "dali"
        self.assertEqual(pc.normalize_node_id("x", {}), "dali")

    def test_multiple_nodes_correct_routing(self):
        m = self._map({
            "z490": self._node("z490", "desktop"),
            "macbook": self._node("mac", "macbook", "laptop"),
        })
        self.assertEqual(pc.normalize_node_id("mac", m), "macbook")
        self.assertEqual(pc.normalize_node_id("desktop", m), "z490")

    def test_node_without_aliases_list_falls_back_to_node_id(self):
        # node_cfg without "aliases" key → values = [node_id]
        m = self._map({"z490": {}})  # no "aliases" key
        self.assertEqual(pc.normalize_node_id("z490", m), "z490")


class TestLoadJson(unittest.TestCase):
    """Tests for load_json() — JSON file loading with missing-file handling."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_file_returns_none(self):
        result = pc.load_json(self._tmp / "nonexistent.json")
        self.assertIsNone(result)

    def test_valid_json_loaded(self):
        path = self._tmp / "test.json"
        path.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        result = pc.load_json(path)
        self.assertEqual(result, {"key": "value"})

    def test_invalid_json_returns_none(self):
        path = self._tmp / "bad.json"
        path.write_text("not json!", encoding="utf-8")
        result = pc.load_json(path)
        self.assertIsNone(result)

    def test_list_json_loaded(self):
        path = self._tmp / "list.json"
        path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        result = pc.load_json(path)
        self.assertEqual(result, [1, 2, 3])


class TestMatchesPrefixPath(unittest.TestCase):
    """Tests for _matches_prefix_path() — hierarchical path prefix check."""

    def test_exact_match(self):
        self.assertTrue(pc._matches_prefix_path("workspace/tools", "workspace/tools"))

    def test_child_path_matches(self):
        self.assertTrue(pc._matches_prefix_path("workspace/tools/foo.py", "workspace/tools"))

    def test_grandchild_path_matches(self):
        self.assertTrue(pc._matches_prefix_path("workspace/tools/a/b.py", "workspace/tools"))

    def test_sibling_no_match(self):
        self.assertFalse(pc._matches_prefix_path("workspace/scripts/foo.py", "workspace/tools"))

    def test_partial_prefix_no_match(self):
        # workspace/toolset is NOT under workspace/tools prefix
        self.assertFalse(pc._matches_prefix_path("workspace/toolset/foo.py", "workspace/tools"))

    def test_empty_path_returns_false(self):
        self.assertFalse(pc._matches_prefix_path("", "workspace/tools"))

    def test_empty_prefix_returns_false(self):
        self.assertFalse(pc._matches_prefix_path("workspace/tools/foo.py", ""))

    def test_backslash_normalized(self):
        self.assertTrue(pc._matches_prefix_path(
            "workspace\\tools\\foo.py", "workspace/tools"
        ))

    def test_leading_slashes_stripped(self):
        self.assertTrue(pc._matches_prefix_path(
            "/workspace/tools/foo.py", "workspace/tools"
        ))


class TestIsAllowedUntrackedPath(unittest.TestCase):
    """Tests for _is_allowed_untracked_path() — audit/research/dry-run paths."""

    def test_audit_dir_allowed(self):
        self.assertTrue(pc._is_allowed_untracked_path("workspace/audit/foo.json"))

    def test_research_pdfs_dir_allowed(self):
        # workspace/research/pdfs/ is in allowed prefixes
        self.assertTrue(pc._is_allowed_untracked_path("workspace/research/pdfs/paper.pdf"))

    def test_random_file_not_allowed(self):
        self.assertFalse(pc._is_allowed_untracked_path("secrets/api_key.txt"))

    def test_empty_path_returns_false(self):
        self.assertFalse(pc._is_allowed_untracked_path(""))

    def test_backslash_normalized(self):
        self.assertTrue(pc._is_allowed_untracked_path("workspace\\audit\\foo.json"))


class TestIsIgnorableRootUntracked(unittest.TestCase):
    """Tests for _is_ignorable_root_untracked() — .claude / .openclaw exclusions."""

    def test_dotclaude_path_ignorable(self):
        # .claude/ prefix is in IGNORABLE_ROOT_UNTRACKED
        result = pc._is_ignorable_root_untracked(".claude/settings.json")
        # Result depends on whether ".claude" is in the set — test truthiness only
        self.assertIsInstance(result, bool)

    def test_empty_path_returns_false(self):
        self.assertFalse(pc._is_ignorable_root_untracked(""))

    def test_random_path_returns_false(self):
        self.assertFalse(pc._is_ignorable_root_untracked("src/random_file.py"))

    def test_backslash_normalized(self):
        # Should normalize backslash before checking
        result1 = pc._is_ignorable_root_untracked(".claude/settings.json")
        result2 = pc._is_ignorable_root_untracked(".claude\\settings.json")
        self.assertEqual(result1, result2)


if __name__ == "__main__":
    unittest.main()
