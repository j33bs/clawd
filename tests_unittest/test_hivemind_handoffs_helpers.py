"""Tests for parse_frontmatter() in workspace/hivemind/hivemind/ingest/handoffs.py.

Stubs relative imports (..models, ..store) before module load.

Covers:
- parse_frontmatter(text) — extracts status/from/date from YAML frontmatter
"""
import importlib.util as _ilu
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "hivemind" / "hivemind" / "ingest" / "handoffs.py"


def _ensure_stubs():
    """Stub hivemind relative dependencies if not already loaded."""
    stub_map = {
        "workspace.hivemind": {"__path__": []},
        "workspace.hivemind.hivemind": {"__path__": []},
        "workspace.hivemind.hivemind.models": {
            "KnowledgeUnit": type("KnowledgeUnit", (), {"__init__": lambda s, **k: None}),
        },
        "workspace.hivemind.hivemind.store": {
            "HiveMindStore": type("HiveMindStore", (), {}),
        },
        "workspace.hivemind.hivemind.ingest": {"__path__": []},
    }
    for name, attrs in stub_map.items():
        if name not in sys.modules:
            m = types.ModuleType(name)
            for k, v in attrs.items():
                setattr(m, k, v)
            sys.modules[name] = m


_ensure_stubs()

_spec = _ilu.spec_from_file_location(
    "workspace.hivemind.hivemind.ingest.handoffs",
    str(MODULE_PATH),
)
hf = _ilu.module_from_spec(_spec)
hf.__package__ = "workspace.hivemind.hivemind.ingest"
sys.modules["workspace.hivemind.hivemind.ingest.handoffs"] = hf
_spec.loader.exec_module(hf)

parse_frontmatter = hf.parse_frontmatter


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter(unittest.TestCase):
    """Tests for parse_frontmatter() — extracts YAML-like frontmatter fields."""

    def test_returns_dict(self):
        self.assertIsInstance(parse_frontmatter(""), dict)

    def test_default_keys_present(self):
        result = parse_frontmatter("")
        self.assertIn("status", result)
        self.assertIn("from", result)
        self.assertIn("date", result)

    def test_empty_text_gives_empty_values(self):
        result = parse_frontmatter("")
        self.assertEqual(result["status"], "")
        self.assertEqual(result["from"], "")
        self.assertEqual(result["date"], "")

    def test_yaml_frontmatter_all_keys(self):
        text = "---\nstatus: open\nfrom: alice\ndate: 2024-01-15\n---\n# Content"
        result = parse_frontmatter(text)
        self.assertEqual(result["status"], "open")
        self.assertEqual(result["from"], "alice")
        self.assertEqual(result["date"], "2024-01-15")

    def test_yaml_frontmatter_partial_keys(self):
        text = "---\nstatus: closed\n---\nSome content"
        result = parse_frontmatter(text)
        self.assertEqual(result["status"], "closed")
        self.assertEqual(result["from"], "")

    def test_no_frontmatter_delimiter_reads_first_40_lines(self):
        text = "status: pending\nfrom: bob\ndate: 2024-03-01"
        result = parse_frontmatter(text)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["from"], "bob")

    def test_case_insensitive_keys(self):
        text = "---\nSTATUS: active\nFROM: charlie\nDATE: 2024-06-01\n---"
        result = parse_frontmatter(text)
        self.assertEqual(result["status"], "active")
        self.assertEqual(result["from"], "charlie")

    def test_whitespace_around_values_stripped(self):
        text = "---\nstatus:   pending   \nfrom:  alice  \n---"
        result = parse_frontmatter(text)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["from"], "alice")

    def test_unknown_keys_ignored(self):
        text = "---\nstatus: open\ntitle: My Doc\nauthor: dave\n---"
        result = parse_frontmatter(text)
        self.assertNotIn("title", result)
        self.assertNotIn("author", result)

    def test_frontmatter_with_content_after(self):
        text = "---\nstatus: merged\nfrom: eve\ndate: 2024-02-20\n---\n\n# Heading\n\nBody text."
        result = parse_frontmatter(text)
        self.assertEqual(result["status"], "merged")
        self.assertEqual(result["from"], "eve")
        self.assertEqual(result["date"], "2024-02-20")

    def test_no_dashes_key_value_in_first_40_lines(self):
        lines = ["line {}".format(i) for i in range(5)]
        lines.insert(2, "status: found")
        text = "\n".join(lines)
        result = parse_frontmatter(text)
        self.assertEqual(result["status"], "found")

    def test_only_three_fields_extracted(self):
        text = "---\nstatus: x\nfrom: y\ndate: z\n---"
        result = parse_frontmatter(text)
        self.assertEqual(set(result.keys()), {"status", "from", "date"})


if __name__ == "__main__":
    unittest.main()
