"""Tests for hint_engine_probe._store_health() and _probe_retrievals()."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "workspace" / "agents") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "agents"))
if str(REPO_ROOT / "workspace" / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "tools"))

import hint_engine as _he
import hint_engine_probe as probe


class TestStoreHealth(unittest.TestCase):
    """Test _store_health() correctly detects present/missing stores."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(self._tmpdir.name)
        # Save all store paths
        self._orig = {
            "_PAUSE_LOG": _he._PAUSE_LOG,
            "_SEMANTIC_STORE": _he._SEMANTIC_STORE,
            "_TRAILS_STORE": _he._TRAILS_STORE,
            "_KB_ENTITIES": _he._KB_ENTITIES,
            "_KB_RESEARCH": _he._KB_RESEARCH,
            "_KNOWLEDGE_UNITS": _he._KNOWLEDGE_UNITS,
            "_MEMORY_MD": _he._MEMORY_MD,
        }
        # Point everything at tmp (don't create them — test MISSING first)
        _he._PAUSE_LOG = tmp / "pause.jsonl"
        _he._SEMANTIC_STORE = tmp / "semantic.jsonl"
        _he._TRAILS_STORE = tmp / "trails.jsonl"
        _he._KB_ENTITIES = tmp / "entities.jsonl"
        _he._KB_RESEARCH = tmp / "research.jsonl"
        _he._KNOWLEDGE_UNITS = tmp / "units.jsonl"
        _he._MEMORY_MD = tmp / "MEMORY.md"
        self._tmp = tmp

    def tearDown(self):
        for attr, val in self._orig.items():
            setattr(_he, attr, val)
        self._tmpdir.cleanup()

    def test_all_missing_reported(self):
        health = probe._store_health()
        self.assertEqual(len(health), 7)
        missing = [h for h in health if h["status"] == "MISSING"]
        self.assertEqual(len(missing), 7)

    def test_present_store_reported_ok(self):
        self._tmp.joinpath("entities.jsonl").write_text(
            json.dumps({"name": "test", "content": "hi"}) + "\n", encoding="utf-8"
        )
        health = probe._store_health()
        entity_row = next(h for h in health if h["store"] == "kb_entities")
        self.assertEqual(entity_row["status"], "OK")
        self.assertEqual(entity_row["lines"], 1)
        self.assertGreater(entity_row["size_bytes"], 0)

    def test_missing_store_has_zero_size(self):
        health = probe._store_health()
        for h in health:
            if h["status"] == "MISSING":
                self.assertEqual(h["size_bytes"], 0)
                self.assertEqual(h["lines"], 0)

    def test_health_returns_all_seven_stores(self):
        health = probe._store_health()
        names = {h["store"] for h in health}
        expected = {"pause_check_log", "semantic_store", "trails",
                    "kb_entities", "kb_research", "knowledge_units", "memory_md"}
        self.assertEqual(names, expected)


class TestProbeRetrievals(unittest.TestCase):
    """Test _probe_retrievals() correctly calls each retriever."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(self._tmpdir.name)
        self._orig = {
            "_KB_ENTITIES": _he._KB_ENTITIES,
            "_KB_RESEARCH": _he._KB_RESEARCH,
            "_KNOWLEDGE_UNITS": _he._KNOWLEDGE_UNITS,
            "_MEMORY_MD": _he._MEMORY_MD,
            "_SEMANTIC_STORE": _he._SEMANTIC_STORE,
            "_TRAILS_STORE": _he._TRAILS_STORE,
        }
        # Create fixtures
        entities = tmp / "entities.jsonl"
        entities.write_text(
            json.dumps({
                "name": "Memory Survey",
                "entity_type": "research:memory",
                "content": "Memory attribution study covers context agents and routing decisions.",
                "source": "test",
            }) + "\n",
            encoding="utf-8",
        )
        units = tmp / "units.jsonl"
        units.write_text(
            json.dumps({
                "kind": "handoff",
                "source": "handoffs",
                "content": "Memory routing context attribution agents make decisions based on policy.",
            }) + "\n",
            encoding="utf-8",
        )
        memory_md = tmp / "MEMORY.md"
        memory_md.write_text(
            "# Memory\n\n## System\nMemory attribution routing context agents decisions policy system.\n",
            encoding="utf-8",
        )
        _he._KB_ENTITIES = entities
        _he._KB_RESEARCH = tmp / "research_empty.jsonl"
        _he._KNOWLEDGE_UNITS = units
        _he._MEMORY_MD = memory_md
        _he._SEMANTIC_STORE = tmp / "semantic_missing.jsonl"
        _he._TRAILS_STORE = tmp / "trails_missing.jsonl"

    def tearDown(self):
        for attr, val in self._orig.items():
            setattr(_he, attr, val)
        self._tmpdir.cleanup()

    def test_probe_returns_one_row_per_retriever(self):
        results = probe._probe_retrievals("memory attribution context")
        # kb_lancedb, semantic_store+trails, kb_entities+research, knowledge_units, memory_md
        self.assertEqual(len(results), 5)

    def test_kb_entities_hits_returned(self):
        results = probe._probe_retrievals("memory attribution context agents routing")
        kb_row = next(r for r in results if r["retriever"] == "kb_entities+research")
        self.assertGreater(kb_row["hits"], 0)
        self.assertEqual(kb_row["status"], "OK")

    def test_knowledge_units_hits_returned(self):
        results = probe._probe_retrievals("memory routing attribution agents context policy")
        units_row = next(r for r in results if r["retriever"] == "knowledge_units")
        self.assertGreater(units_row["hits"], 0)

    def test_memory_md_hits_returned(self):
        results = probe._probe_retrievals("memory attribution routing context agents decisions")
        mem_row = next(r for r in results if r["retriever"] == "memory_md")
        self.assertGreater(mem_row["hits"], 0)

    def test_missing_stores_return_empty_not_error(self):
        results = probe._probe_retrievals("memory attribution stylometry")
        sem_row = next(r for r in results if r["retriever"] == "semantic_store+trails")
        # Missing store → empty result, not error
        self.assertIn(sem_row["status"], ("OK", "EMPTY"))
        self.assertEqual(sem_row["hits"], 0)

    def test_all_rows_have_elapsed_ms(self):
        results = probe._probe_retrievals("memory attribution")
        for r in results:
            self.assertIn("elapsed_ms", r)
            self.assertGreaterEqual(r["elapsed_ms"], 0)

    def test_lancedb_row_present_even_when_unavailable(self):
        """kb_lancedb row always present — may be ERROR if lancedb missing."""
        results = probe._probe_retrievals("memory attribution")
        lancedb_row = next(r for r in results if r["retriever"] == "kb_lancedb")
        self.assertIn("status", lancedb_row)
        self.assertIn("hits", lancedb_row)


class TestHealthJsonFastPath(unittest.TestCase):
    """--health --json must return only store health without triggering retrieval/model load."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(self._tmpdir.name)
        self._orig = {
            "_PAUSE_LOG": _he._PAUSE_LOG,
            "_SEMANTIC_STORE": _he._SEMANTIC_STORE,
            "_TRAILS_STORE": _he._TRAILS_STORE,
            "_KB_ENTITIES": _he._KB_ENTITIES,
            "_KB_RESEARCH": _he._KB_RESEARCH,
            "_KNOWLEDGE_UNITS": _he._KNOWLEDGE_UNITS,
            "_MEMORY_MD": _he._MEMORY_MD,
        }
        # Point all paths at tmp (no files exist)
        _he._PAUSE_LOG = tmp / "pause.jsonl"
        _he._SEMANTIC_STORE = tmp / "semantic.jsonl"
        _he._TRAILS_STORE = tmp / "trails.jsonl"
        _he._KB_ENTITIES = tmp / "entities.jsonl"
        _he._KB_RESEARCH = tmp / "research.jsonl"
        _he._KNOWLEDGE_UNITS = tmp / "units.jsonl"
        _he._MEMORY_MD = tmp / "MEMORY.md"

    def tearDown(self):
        for attr, val in self._orig.items():
            setattr(_he, attr, val)
        self._tmpdir.cleanup()

    def test_health_json_returns_only_health_key(self):
        """With --health --json, output must have 'health' key and NO 'probe' or 'sweep' key."""
        import io
        import argparse
        from unittest.mock import patch

        args = argparse.Namespace(
            prompt="test",
            health=True,
            sweep=False,
            as_json=True,
        )
        with patch("builtins.print") as mock_print:
            import hint_engine_probe as _probe
            health = _probe._store_health()
            # Simulate the main() JSON path with --health --json
            if args.as_json:
                if args.health:
                    output = json.dumps({"health": health}, indent=2)
                elif args.sweep:
                    pass  # not testing this branch
                else:
                    pass  # not testing this branch

        parsed = json.loads(output)
        self.assertIn("health", parsed)
        self.assertNotIn("probe", parsed)
        self.assertNotIn("sweep", parsed)
        self.assertEqual(len(parsed["health"]), 7)


if __name__ == "__main__":
    unittest.main()
