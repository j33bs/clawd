"""Tests for parse_memory_chunks() in workspace/hivemind/hivemind/ingest/memory_md.py.

Stubs relative imports (..models, ..store) before module load.

Covers:
- parse_memory_chunks(text) — splits markdown into typed chunks (fact/lesson)
"""
import importlib.util as _ilu
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "hivemind" / "hivemind" / "ingest" / "memory_md.py"


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
    "workspace.hivemind.hivemind.ingest.memory_md",
    str(MODULE_PATH),
)
mmd = _ilu.module_from_spec(_spec)
mmd.__package__ = "workspace.hivemind.hivemind.ingest"
sys.modules["workspace.hivemind.hivemind.ingest.memory_md"] = mmd
_spec.loader.exec_module(mmd)

parse_memory_chunks = mmd.parse_memory_chunks


# ---------------------------------------------------------------------------
# parse_memory_chunks
# ---------------------------------------------------------------------------


class TestParseMemoryChunks(unittest.TestCase):
    """Tests for parse_memory_chunks() — splits markdown into fact/lesson chunks."""

    def test_empty_text_returns_empty_list(self):
        self.assertEqual(parse_memory_chunks(""), [])

    def test_returns_list(self):
        result = parse_memory_chunks("## Header\n- item")
        self.assertIsInstance(result, list)

    def test_each_chunk_has_kind_and_content(self):
        chunks = parse_memory_chunks("## Header\n- item")
        for chunk in chunks:
            self.assertIn("kind", chunk)
            self.assertIn("content", chunk)

    def test_single_header_with_bullets_one_chunk(self):
        text = "## Facts\n- alpha\n- beta\n- gamma"
        chunks = parse_memory_chunks(text)
        self.assertEqual(len(chunks), 1)

    def test_fact_kind_default(self):
        chunks = parse_memory_chunks("## Notes\n- some note")
        self.assertEqual(chunks[0]["kind"], "fact")

    def test_lesson_keyword_in_header_gives_lesson_kind(self):
        chunks = parse_memory_chunks("## Lessons Learned\n- be careful")
        self.assertEqual(chunks[0]["kind"], "lesson")

    def test_learned_keyword_in_content_gives_lesson_kind(self):
        chunks = parse_memory_chunks("## Review\n- I learned to test first")
        self.assertEqual(chunks[0]["kind"], "lesson")

    def test_mistake_keyword_gives_lesson_kind(self):
        chunks = parse_memory_chunks("## Retrospective\n- made a mistake here")
        self.assertEqual(chunks[0]["kind"], "lesson")

    def test_retro_keyword_in_header_gives_lesson_kind(self):
        chunks = parse_memory_chunks("## Retro\n- issues found")
        self.assertEqual(chunks[0]["kind"], "lesson")

    def test_multiple_headers_multiple_chunks(self):
        text = "## Facts\n- fact one\n## Lessons\n- lesson one"
        chunks = parse_memory_chunks(text)
        self.assertEqual(len(chunks), 2)

    def test_content_includes_header(self):
        chunks = parse_memory_chunks("## My Header\n- item")
        self.assertIn("My Header", chunks[0]["content"])

    def test_bullets_and_text_split_into_separate_chunks(self):
        # Bullet block then text block → 2 chunks
        text = "## Header\n- bullet item\nplain text line"
        chunks = parse_memory_chunks(text)
        self.assertEqual(len(chunks), 2)

    def test_text_block_is_fact(self):
        chunks = parse_memory_chunks("## Section\nThis is plain text.")
        self.assertEqual(chunks[0]["kind"], "fact")

    def test_blank_lines_dont_create_extra_chunks(self):
        text = "## Section\n- item one\n\n- item two"
        chunks = parse_memory_chunks(text)
        # Both are bullets; blank line doesn't flush
        self.assertEqual(len(chunks), 1)

    def test_chunk_without_header_treated_as_fact(self):
        # Text before any header
        chunks = parse_memory_chunks("- orphan bullet")
        self.assertEqual(len(chunks), 1)

    def test_h3_header_treated_same_as_h2(self):
        chunks = parse_memory_chunks("### Sub-section\n- item")
        self.assertEqual(len(chunks), 1)

    def test_multiple_bullet_items_in_content(self):
        text = "## List\n- alpha\n- beta\n- gamma"
        chunks = parse_memory_chunks(text)
        self.assertIn("alpha", chunks[0]["content"])
        self.assertIn("beta", chunks[0]["content"])
        self.assertIn("gamma", chunks[0]["content"])


if __name__ == "__main__":
    unittest.main()
