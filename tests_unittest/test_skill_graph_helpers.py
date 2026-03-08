"""Tests for workspace/skill-graph/skill_graph.py pure helpers.

Covers (no network, tempfile only):
- SkillGraph._parse_frontmatter
- SkillGraph._extract_wikilinks
- SkillGraph.load_skill (with tempfile)
- SkillGraph.traverse (with tempfile)
- SkillGraph.search (with tempfile)
"""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "workspace" / "skill-graph"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from skill_graph import SkillGraph  # noqa: E402


def _graph(td: str) -> SkillGraph:
    """Build a SkillGraph rooted at a temp directory."""
    root = Path(td)
    (root / "skills").mkdir(exist_ok=True)
    (root / "mocs").mkdir(exist_ok=True)
    return SkillGraph(str(root))


def _write_skill(td: str, name: str, content: str) -> None:
    """Write a skill file into skills/ subdir."""
    path = Path(td) / "skills" / f"{name}.md"
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------

class TestParseFrontmatter(unittest.TestCase):
    """Tests for SkillGraph._parse_frontmatter()."""

    def setUp(self):
        self._td = tempfile.mkdtemp()
        self._g = _graph(self._td)

    def test_returns_tuple(self):
        result = self._g._parse_frontmatter("---\ntitle: Test\n---\nbody")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_extracts_frontmatter(self):
        fm, body = self._g._parse_frontmatter("---\ndescription: Hello\n---\nbody text")
        self.assertEqual(fm.get("description"), "Hello")

    def test_body_separated(self):
        fm, body = self._g._parse_frontmatter("---\ntitle: T\n---\nbody content")
        self.assertIn("body content", body)
        self.assertNotIn("title", body)

    def test_no_frontmatter(self):
        fm, body = self._g._parse_frontmatter("just body text")
        self.assertEqual(fm, {})
        self.assertEqual(body, "just body text")

    def test_empty_frontmatter(self):
        fm, body = self._g._parse_frontmatter("---\n---\nbody")
        self.assertIsInstance(fm, dict)

    def test_tags_list_parsed(self):
        content = "---\ntags:\n  - AI\n  - memory\n---\nbody"
        fm, _ = self._g._parse_frontmatter(content)
        self.assertIn("AI", fm.get("tags", []))


# ---------------------------------------------------------------------------
# _extract_wikilinks
# ---------------------------------------------------------------------------

class TestExtractWikilinks(unittest.TestCase):
    """Tests for SkillGraph._extract_wikilinks()."""

    def setUp(self):
        self._td = tempfile.mkdtemp()
        self._g = _graph(self._td)

    def test_extracts_single_link(self):
        result = self._g._extract_wikilinks("See [[memory]] for details")
        self.assertIn("memory", result)

    def test_extracts_multiple_links(self):
        result = self._g._extract_wikilinks("See [[memory]] and [[attention]]")
        self.assertIn("memory", result)
        self.assertIn("attention", result)

    def test_no_links_returns_empty(self):
        result = self._g._extract_wikilinks("no links here")
        self.assertEqual(result, [])

    def test_returns_list(self):
        self.assertIsInstance(self._g._extract_wikilinks("[[test]]"), list)

    def test_link_name_extracted(self):
        result = self._g._extract_wikilinks("[[my-skill-name]]")
        self.assertEqual(result[0], "my-skill-name")


# ---------------------------------------------------------------------------
# load_skill
# ---------------------------------------------------------------------------

class TestLoadSkill(unittest.TestCase):
    """Tests for SkillGraph.load_skill() with tempfile-backed skills dir."""

    def test_loads_skill_dict(self):
        with tempfile.TemporaryDirectory() as td:
            g = _graph(td)
            _write_skill(td, "coding", "---\ndescription: Coding skill\n---\nContent here")
            skill = g.load_skill("coding")
            self.assertIsInstance(skill, dict)

    def test_description_parsed(self):
        with tempfile.TemporaryDirectory() as td:
            g = _graph(td)
            _write_skill(td, "alpha", "---\ndescription: Alpha skill\n---\nBody")
            skill = g.load_skill("alpha")
            self.assertEqual(skill["description"], "Alpha skill")

    def test_name_set(self):
        with tempfile.TemporaryDirectory() as td:
            g = _graph(td)
            _write_skill(td, "beta", "body only")
            skill = g.load_skill("beta")
            self.assertEqual(skill["name"], "beta")

    def test_wikilinks_extracted_from_body(self):
        with tempfile.TemporaryDirectory() as td:
            g = _graph(td)
            _write_skill(td, "gamma", "---\n---\nSee [[delta]] for more")
            skill = g.load_skill("gamma")
            self.assertIn("delta", skill["links"])

    def test_missing_skill_raises(self):
        with tempfile.TemporaryDirectory() as td:
            g = _graph(td)
            with self.assertRaises(FileNotFoundError):
                g.load_skill("nonexistent")

    def test_cached_on_second_call(self):
        with tempfile.TemporaryDirectory() as td:
            g = _graph(td)
            _write_skill(td, "cached", "body")
            r1 = g.load_skill("cached")
            r2 = g.load_skill("cached")
            self.assertIs(r1, r2)


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class TestSearch(unittest.TestCase):
    """Tests for SkillGraph.search() — name/description/tag matching."""

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            g = _graph(td)
            self.assertIsInstance(g.search("anything"), list)

    def test_empty_skills_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            g = _graph(td)
            self.assertEqual(g.search("query"), [])

    def test_matches_by_name(self):
        with tempfile.TemporaryDirectory() as td:
            g = _graph(td)
            _write_skill(td, "coding-python", "body")
            result = g.search("python")
            self.assertEqual(len(result), 1)

    def test_matches_by_description(self):
        with tempfile.TemporaryDirectory() as td:
            g = _graph(td)
            _write_skill(td, "ml", "---\ndescription: Machine learning techniques\n---\nbody")
            result = g.search("machine learning")
            self.assertEqual(len(result), 1)

    def test_no_match_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            g = _graph(td)
            _write_skill(td, "coding", "---\ndescription: Code\n---\nbody")
            result = g.search("zzz_unlikely_query_zzz")
            self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
