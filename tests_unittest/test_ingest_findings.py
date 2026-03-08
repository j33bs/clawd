"""Tests for ingest_findings.py — findings.json → KB research_import.jsonl."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import ingest_findings as ig


def _make_question(topic="test topic", ts="2026-03-07T00:00:00Z",
                   novelty_reason="accepted", seed="seed topic",
                   question="What is the open question about this topic?",
                   overlap=0.1, similarity=0.2):
    return {
        "from_topic": topic,
        "question": question,
        "seed_topic": seed,
        "novelty_reason": novelty_reason,
        "overlap_max": overlap,
        "similarity_max": similarity,
        "timestamp": ts,
    }


class TestEntryKey(unittest.TestCase):
    def test_same_topic_ts_gives_same_key(self):
        q = _make_question(topic="attribution", ts="2026-03-07T00:00:00Z")
        k1 = ig._entry_key(q)
        k2 = ig._entry_key(q)
        self.assertEqual(k1, k2)

    def test_different_ts_gives_different_key(self):
        q1 = _make_question(ts="2026-03-07T00:00:00Z")
        q2 = _make_question(ts="2026-03-08T00:00:00Z")
        self.assertNotEqual(ig._entry_key(q1), ig._entry_key(q2))

    def test_key_is_16_hex_chars(self):
        key = ig._entry_key(_make_question())
        self.assertEqual(len(key), 16)
        int(key, 16)  # Should not raise

    def test_different_topics_give_different_keys(self):
        q1 = _make_question(topic="a")
        q2 = _make_question(topic="b")
        self.assertNotEqual(ig._entry_key(q1), ig._entry_key(q2))


class TestFormatEntity(unittest.TestCase):
    def test_entity_has_required_fields(self):
        q = _make_question(topic="stylometry", question="How does stylometry work across corpora?")
        entity = ig._format_entity(q)
        self.assertIn("name", entity)
        self.assertIn("entity_type", entity)
        self.assertIn("content", entity)
        self.assertIn("source", entity)
        self.assertIn("metadata", entity)

    def test_entity_type_is_wanderer(self):
        entity = ig._format_entity(_make_question())
        self.assertEqual(entity["entity_type"], "research:wanderer")

    def test_name_contains_topic(self):
        entity = ig._format_entity(_make_question(topic="dispositional signatures"))
        self.assertIn("dispositional signatures", entity["name"])

    def test_content_contains_question(self):
        q = _make_question(question="What does dispositional attribution mean across multiple topics?")
        entity = ig._format_entity(q)
        self.assertIn("What does dispositional attribution", entity["content"])

    def test_long_question_truncated(self):
        long_q = "A" * 400
        entity = ig._format_entity(_make_question(question=long_q))
        self.assertLessEqual(len(entity["content"].split("Generated question:")[1].split("\n")[0].strip()), 305)


class TestIngest(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig = {
            "FINDINGS_FILE": ig.FINDINGS_FILE,
            "INGEST_STATE": ig.INGEST_STATE,
            "KB_IMPORT": ig.KB_IMPORT,
        }
        ig.FINDINGS_FILE = self._tmp / "findings.json"
        ig.INGEST_STATE = self._tmp / ".findings_ingested.json"
        ig.KB_IMPORT = self._tmp / "kb" / "research_import.jsonl"

    def tearDown(self):
        for attr, val in self._orig.items():
            setattr(ig, attr, val)
        self._tmpdir.cleanup()

    def _write_findings(self, questions: list) -> None:
        ig.FINDINGS_FILE.write_text(
            json.dumps({"questions_generated": questions}), encoding="utf-8"
        )

    def test_no_findings_file(self):
        result = ig.ingest()
        self.assertEqual(result["status"], "no_findings")

    def test_empty_questions(self):
        self._write_findings([])
        result = ig.ingest()
        self.assertEqual(result["status"], "no_findings")

    def test_accepted_findings_ingested(self):
        questions = [_make_question(novelty_reason="accepted", topic=f"topic_{i}") for i in range(3)]
        self._write_findings(questions)
        result = ig.ingest()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["ingested"], 3)
        # Check KB file was written
        lines = ig.KB_IMPORT.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 3)

    def test_fallback_findings_skipped_by_default(self):
        questions = [
            _make_question(novelty_reason="accepted"),
            _make_question(novelty_reason="fallback_best_of_5", ts="2026-03-07T01:00:00Z"),
        ]
        self._write_findings(questions)
        result = ig.ingest()
        self.assertEqual(result["ingested"], 1)

    def test_fallback_included_with_force_all(self):
        questions = [
            _make_question(novelty_reason="accepted"),
            _make_question(novelty_reason="fallback_best_of_5", ts="2026-03-07T01:00:00Z"),
        ]
        self._write_findings(questions)
        result = ig.ingest(force_all=True)
        self.assertEqual(result["ingested"], 2)

    def test_idempotent_on_second_run(self):
        questions = [_make_question(novelty_reason="accepted")]
        self._write_findings(questions)
        ig.ingest()
        result = ig.ingest()
        self.assertEqual(result["status"], "up_to_date")
        self.assertEqual(result["ingested"], 0)
        self.assertEqual(result["skipped"], 1)

    def test_dry_run_does_not_write(self):
        questions = [_make_question(novelty_reason="accepted")]
        self._write_findings(questions)
        result = ig.ingest(dry_run=True)
        self.assertEqual(result["status"], "dry_run")
        self.assertFalse(ig.KB_IMPORT.exists())

    def test_kb_import_entries_are_valid_json(self):
        questions = [_make_question(novelty_reason="accepted", topic=f"t{i}") for i in range(5)]
        self._write_findings(questions)
        ig.ingest()
        for line in ig.KB_IMPORT.read_text(encoding="utf-8").splitlines():
            obj = json.loads(line)  # Should not raise
            self.assertIn("name", obj)
            self.assertIn("content", obj)

    def test_state_file_tracks_ingested_keys(self):
        questions = [_make_question(novelty_reason="accepted")]
        self._write_findings(questions)
        ig.ingest()
        state = json.loads(ig.INGEST_STATE.read_text(encoding="utf-8"))
        self.assertIn("ingested", state)
        self.assertEqual(len(state["ingested"]), 1)


if __name__ == "__main__":
    unittest.main()
