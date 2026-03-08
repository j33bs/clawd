import json
import tempfile
import unittest
from pathlib import Path

from workspace.agents.hint_engine import HintEngine
import workspace.agents.hint_engine as hint_engine_module


class _DummyRouter:
    def __init__(self):
        self.calls = []

    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
        self.calls.append(
            {
                "intent": intent,
                "payload": dict(payload or {}),
                "context_metadata": dict(context_metadata or {}),
                "validate_fn": validate_fn,
            }
        )
        if intent == "hint_shepherding":
            return {
                "ok": True,
                "text": "Evidence first. Treat the hint as conjecture until verified.",
                "provider": "openai_gpt52_chat",
                "model": "gpt-5.2-chat-latest",
                "request_id": "req-hint-1",
                "reason_code": "success",
            }
        return {
            "ok": True,
            "text": "Final answer with explicit evidence and uncertainty markers.",
            "provider": "openai_gpt53_codex",
            "model": "gpt-5.3-codex",
            "request_id": "req-completion-1",
            "reason_code": "success",
        }


class TestHintEnginePolicyRouter(unittest.TestCase):
    def test_hint_requests_use_policy_router_path(self):
        router = _DummyRouter()
        engine = HintEngine(router=router)

        out = engine.request_hint("Explain the failure mode", "logic", "uncertain local output")

        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["provider"], "openai_gpt52_chat")
        self.assertEqual(out["model"], "gpt-5.2-chat-latest")
        self.assertEqual(out["request_id"], "req-hint-1")
        self.assertEqual(router.calls[0]["intent"], "hint_shepherding")

    def test_completion_fallback_uses_policy_router_path(self):
        router = _DummyRouter()
        engine = HintEngine(router=router)

        out = engine.request_completion_fallback("Need a full fallback answer")

        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["provider"], "openai_gpt53_codex")
        self.assertEqual(out["model"], "gpt-5.3-codex")
        self.assertEqual(out["request_id"], "req-completion-1")
        self.assertEqual(router.calls[0]["intent"], "completion_fallback")


class TestPauseStuckSignal(unittest.TestCase):
    """Test _pause_stuck_signal() with mocked pause_check_log files."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_log = hint_engine_module._PAUSE_LOG
        self._log_path = Path(self._tmpdir.name) / "pause_check_log.jsonl"
        hint_engine_module._PAUSE_LOG = self._log_path

    def tearDown(self):
        hint_engine_module._PAUSE_LOG = self._orig_log
        self._tmpdir.cleanup()

    def _write_entries(self, entries):
        with self._log_path.open("w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def _make_entry(self, decision="silence", fills_space=0.85, value_add=0.0):
        return {
            "ts": "2026-03-07T00:00:00Z",
            "decision": decision,
            "signals": {"fills_space": fills_space, "value_add": value_add},
        }

    def test_no_log_returns_false(self):
        from workspace.agents.hint_engine import _pause_stuck_signal
        self.assertFalse(_pause_stuck_signal())

    def test_identical_entries_above_threshold_returns_true(self):
        from workspace.agents.hint_engine import _pause_stuck_signal
        entries = [self._make_entry() for _ in range(5)]
        self._write_entries(entries)
        self.assertTrue(_pause_stuck_signal())

    def test_diverse_entries_returns_false(self):
        from workspace.agents.hint_engine import _pause_stuck_signal
        entries = [
            self._make_entry("silence", 0.85, 0.0),
            self._make_entry("respond", 0.2, 0.8),
            self._make_entry("silence", 0.85, 0.0),
            self._make_entry("respond", 0.3, 0.7),
        ]
        self._write_entries(entries)
        self.assertFalse(_pause_stuck_signal())

    def test_below_threshold_returns_false(self):
        from workspace.agents.hint_engine import _pause_stuck_signal
        entries = [self._make_entry() for _ in range(3)]  # < _STUCK_THRESHOLD=4
        self._write_entries(entries)
        self.assertFalse(_pause_stuck_signal())

    def test_should_force_escalate_reflects_stuck(self):
        entries = [self._make_entry() for _ in range(5)]
        self._write_entries(entries)
        engine = HintEngine()
        self.assertTrue(engine.should_force_escalate())

    def test_stuck_annotation_in_hint_prompt(self):
        """When stuck, the hint prompt should include the STUCK system note."""
        entries = [self._make_entry() for _ in range(5)]
        self._write_entries(entries)

        router = _DummyRouter()
        engine = HintEngine(router=router)
        engine.request_hint("What is the correct answer?", "logic", "uncertain")

        # The hint prompt passed to the router should include the stuck note
        prompt_sent = router.calls[0]["payload"]["prompt"]
        self.assertIn("STUCK", prompt_sent)
        self.assertIn("Escalate with high confidence", prompt_sent)


class TestSemanticContext(unittest.TestCase):
    """Test _fetch_semantic_context() with mocked store files."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_semantic = hint_engine_module._SEMANTIC_STORE
        self._orig_trails = hint_engine_module._TRAILS_STORE
        self._store_path = Path(self._tmpdir.name) / "semantic_store.jsonl"
        hint_engine_module._SEMANTIC_STORE = self._store_path
        hint_engine_module._TRAILS_STORE = Path(self._tmpdir.name) / "trails.jsonl"

    def tearDown(self):
        hint_engine_module._SEMANTIC_STORE = self._orig_semantic
        hint_engine_module._TRAILS_STORE = self._orig_trails
        self._tmpdir.cleanup()

    def test_missing_store_returns_empty(self):
        from workspace.agents.hint_engine import _fetch_semantic_context
        result = _fetch_semantic_context("being attribution stylometry")
        self.assertEqual(result, "")

    def test_matching_entry_returned(self):
        from workspace.agents.hint_engine import _fetch_semantic_context
        entry = {
            "fact": "Dispositional signatures persist across topics in correspondence corpus.",
            "topics": ["attribution", "being", "stylometry"],
            "entities": ["Claude Code", "Grok"],
            "support_count": 3,
        }
        with self._store_path.open("w") as f:
            f.write(json.dumps(entry) + "\n")

        result = _fetch_semantic_context("being attribution stylometry")
        self.assertIn("[semantic]", result)
        self.assertIn("Dispositional", result)

    def test_no_overlap_returns_empty(self):
        from workspace.agents.hint_engine import _fetch_semantic_context
        entry = {
            "fact": "Completely unrelated content about something else entirely.",
            "topics": ["xyz", "abc"],
            "entities": [],
            "support_count": 1,
        }
        with self._store_path.open("w") as f:
            f.write(json.dumps(entry) + "\n")

        result = _fetch_semantic_context("being attribution stylometry")
        self.assertEqual(result, "")


class TestMemoryMdContext(unittest.TestCase):
    """Test _fetch_memory_md_context() with mocked MEMORY.md."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_memory_md = hint_engine_module._MEMORY_MD
        self._memory_path = Path(self._tmpdir.name) / "MEMORY.md"
        hint_engine_module._MEMORY_MD = self._memory_path

    def tearDown(self):
        hint_engine_module._MEMORY_MD = self._orig_memory_md
        self._tmpdir.cleanup()

    def test_missing_file_returns_empty(self):
        from workspace.agents.hint_engine import _fetch_memory_md_context
        result = _fetch_memory_md_context("memory stylometry attribution")
        self.assertEqual(result, "")

    def test_matching_section_returned(self):
        from workspace.agents.hint_engine import _fetch_memory_md_context
        content = (
            "# Claude Code Memory\n\n"
            "## Current state\n"
            "- INV-003b CLOSED. Stylometry attribution confirmed across corpus. "
            "Memory system wired with policy router for context-aware decisions.\n\n"
            "## Branch\n"
            "- claude-code/governance-session\n"
        )
        self._memory_path.write_text(content, encoding="utf-8")
        result = _fetch_memory_md_context("stylometry attribution memory corpus")
        self.assertIn("[memory]", result)
        self.assertIn("Current state", result)

    def test_low_overlap_section_excluded(self):
        from workspace.agents.hint_engine import _fetch_memory_md_context
        content = (
            "# Claude Code Memory\n\n"
            "## Branch\n"
            "- governance branch active\n\n"
        )
        self._memory_path.write_text(content, encoding="utf-8")
        # Threshold is 3 — "Branch" section has very few tokens
        result = _fetch_memory_md_context("stylometry attribution memory corpus research")
        self.assertEqual(result, "")

    def test_multiple_sections_capped_at_k(self):
        from workspace.agents.hint_engine import _fetch_memory_md_context
        section_body = (
            "Memory stylometry attribution research corpus analysis context "
            "wired policy router decision making evidence.\n"
        )
        sections = "\n".join(
            f"## Section {i}\n{section_body}" for i in range(5)
        )
        content = f"# Header\n\n{sections}"
        self._memory_path.write_text(content, encoding="utf-8")
        result = _fetch_memory_md_context("memory stylometry attribution corpus", k=2)
        self.assertLessEqual(result.count("[memory]"), 2)

    def test_daily_distillations_matched(self):
        from workspace.agents.hint_engine import _fetch_memory_md_context
        content = (
            "# Claude Code Memory\n\n"
            "## Daily Distillations\n"
            "### 2026-03-07 (dream-summary)\n"
            "- Total events: 1082 | successes: 0 | failures: 5\n"
            "- Top event types: tacti_cr.prefetch, semantic immune, quarantined\n"
            "- Failure-dominant session review required\n"
        )
        self._memory_path.write_text(content, encoding="utf-8")
        result = _fetch_memory_md_context("tacti prefetch failure session review")
        self.assertIn("[memory]", result)
        self.assertIn("Daily Distillations", result)


class TestKBEntitiesContext(unittest.TestCase):
    """Test _fetch_kb_entities_context() with mocked KB store files."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_kb_entities = hint_engine_module._KB_ENTITIES
        self._orig_kb_research = hint_engine_module._KB_RESEARCH
        self._entities_path = Path(self._tmpdir.name) / "entities.jsonl"
        self._research_path = Path(self._tmpdir.name) / "research_import.jsonl"
        hint_engine_module._KB_ENTITIES = self._entities_path
        hint_engine_module._KB_RESEARCH = self._research_path

    def tearDown(self):
        hint_engine_module._KB_ENTITIES = self._orig_kb_entities
        hint_engine_module._KB_RESEARCH = self._orig_kb_research
        self._tmpdir.cleanup()

    def _write_entity(self, path, name, entity_type, content):
        entry = {"name": name, "entity_type": entity_type, "content": content, "source": "test"}
        with path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def test_missing_stores_return_empty(self):
        from workspace.agents.hint_engine import _fetch_kb_entities_context
        result = _fetch_kb_entities_context("memory attribution context")
        self.assertEqual(result, "")

    def test_matching_entity_returned(self):
        from workspace.agents.hint_engine import _fetch_kb_entities_context
        self._write_entity(
            self._entities_path,
            "Memory Survey 2025",
            "research:memory",
            "Memory is a core capability of foundation model-based agents including attribution.",
        )
        result = _fetch_kb_entities_context("memory attribution agents")
        self.assertIn("[kb-entity]", result)
        self.assertIn("Memory Survey", result)

    def test_research_import_searched(self):
        from workspace.agents.hint_engine import _fetch_kb_entities_context
        self._write_entity(
            self._research_path,
            "Wanderer: dispositional stylometry",
            "research:wanderer",
            "Dispositional stylometry question about attribution across corpus topics.",
        )
        result = _fetch_kb_entities_context("stylometry attribution corpus")
        self.assertIn("[kb-entity]", result)
        self.assertIn("Wanderer", result)

    def test_no_overlap_returns_empty(self):
        from workspace.agents.hint_engine import _fetch_kb_entities_context
        self._write_entity(
            self._entities_path,
            "Unrelated Entry",
            "research:other",
            "Completely different topic about something entirely unrelated to anything.",
        )
        result = _fetch_kb_entities_context("memory stylometry attribution")
        self.assertEqual(result, "")

    def test_result_capped_at_k(self):
        from workspace.agents.hint_engine import _fetch_kb_entities_context
        # Write 5 matching entries
        for i in range(5):
            self._write_entity(
                self._entities_path,
                f"Memory Study {i}",
                "research:memory",
                f"Memory attribution study {i} about context and agents across topics.",
            )
        result = _fetch_kb_entities_context("memory attribution context agents", k=2)
        # Should return at most k=2 results
        self.assertLessEqual(result.count("[kb-entity]"), 2)


class TestKnowledgeUnitsContext(unittest.TestCase):
    """Test _fetch_knowledge_units_context() with mocked knowledge_units.jsonl."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_units = hint_engine_module._KNOWLEDGE_UNITS
        self._units_path = Path(self._tmpdir.name) / "knowledge_units.jsonl"
        hint_engine_module._KNOWLEDGE_UNITS = self._units_path

    def tearDown(self):
        hint_engine_module._KNOWLEDGE_UNITS = self._orig_units
        self._tmpdir.cleanup()

    def _write_unit(self, kind, source, content):
        entry = {"kind": kind, "source": source, "content": content}
        with self._units_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def test_missing_file_returns_empty(self):
        from workspace.agents.hint_engine import _fetch_knowledge_units_context
        result = _fetch_knowledge_units_context("memory attribution stylometry")
        self.assertEqual(result, "")

    def test_memory_md_entry_returned(self):
        from workspace.agents.hint_engine import _fetch_knowledge_units_context
        self._write_unit(
            "fact",
            "memory_md",
            "Multi-Agent System: main agent handles Telegram messages and memory attribution routing.",
        )
        result = _fetch_knowledge_units_context("memory agent routing attribution")
        self.assertIn("[units]", result)
        self.assertIn("memory_md", result)

    def test_code_snippet_skipped(self):
        from workspace.agents.hint_engine import _fetch_knowledge_units_context
        self._write_unit(
            "code_snippet",
            "git:abc123",
            "Memory attribution routing multi-agent system handles context carefully.",
        )
        result = _fetch_knowledge_units_context("memory attribution routing")
        self.assertEqual(result, "")

    def test_git_source_skipped(self):
        from workspace.agents.hint_engine import _fetch_knowledge_units_context
        self._write_unit(
            "fact",
            "git:def456",
            "Memory attribution system routes context across multiple agents.",
        )
        result = _fetch_knowledge_units_context("memory attribution context")
        self.assertEqual(result, "")

    def test_trivially_short_content_skipped(self):
        from workspace.agents.hint_engine import _fetch_knowledge_units_context
        self._write_unit("fact", "tacti_cr.temporal", "recent")
        result = _fetch_knowledge_units_context("recent memory attribution")
        self.assertEqual(result, "")

    def test_handoff_entry_returned(self):
        from workspace.agents.hint_engine import _fetch_knowledge_units_context
        self._write_unit(
            "handoff",
            "handoffs",
            "Handoff: audit completed. Memory system wired with attribution routing. "
            "All agents use policy_router for context-aware decisions and memory retrieval.",
        )
        result = _fetch_knowledge_units_context("memory attribution policy routing")
        self.assertIn("[units]", result)
        self.assertIn("handoffs", result)


if __name__ == "__main__":
    unittest.main()
