import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from research_wanderer import (  # noqa: E402
    evaluate_novelty,
    parse_wander_log_questions,
    researcher_mode_enabled,
    select_question,
)


class TestResearchWandererNovelty(unittest.TestCase):
    def test_researcher_flag_default_off(self):
        old = os.environ.pop("OPENCLAW_WANDERER_RESEARCHER", None)
        try:
            self.assertFalse(researcher_mode_enabled())
        finally:
            if old is not None:
                os.environ["OPENCLAW_WANDERER_RESEARCHER"] = old

    def test_researcher_flag_on(self):
        os.environ["OPENCLAW_WANDERER_RESEARCHER"] = "1"
        try:
            self.assertTrue(researcher_mode_enabled())
        finally:
            os.environ.pop("OPENCLAW_WANDERER_RESEARCHER", None)

    def test_overlap_rejected_when_gt_half(self):
        recent = ["How might active inference explain distributed AI identity continuity?"]
        candidate = "How might active inference explain distributed AI identity continuity in agents?"
        decision = evaluate_novelty(candidate, recent)
        self.assertFalse(decision.accepted)
        self.assertGreater(decision.overlap_max, 0.5)

    def test_similarity_rejected_when_gt_threshold(self):
        recent = ["memory consolidation replay mechanisms in ai systems"]
        candidate = "ai systems memory consolidation replay mechanisms"
        decision = evaluate_novelty(candidate, recent)
        self.assertFalse(decision.accepted)
        self.assertGreater(decision.similarity_max, 0.7)

    def test_select_question_regenerates_and_accepts_novel(self):
        recent = [
            "How might topic x intersect with active inference, given open loop: open loop unavailable? What measurable prediction would falsify this claim?",
            "How might topic x intersect with global workspace theory, given open loop: open loop unavailable? Where does this break under adversarial conditions?",
        ]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            topics = tmp / "TOPICS.md"
            topics.write_text("- active inference\n- neuromodulation\n", encoding="utf-8")
            oq = tmp / "OPEN_QUESTIONS.md"
            oq.write_text("2026-02-25 | What weak signal have we ignored?\n", encoding="utf-8")

            import random

            q, meta = select_question("topic y", recent, rng=random.Random(7), topics_path=topics, oq_path=oq, max_attempts=5)
            self.assertIn("topic y", q)
            self.assertLessEqual(meta["overlap_max"], 0.5)
            self.assertLessEqual(meta["similarity_max"], 0.7)
            self.assertGreaterEqual(meta["attempts"], 1)

    def test_parse_wander_log_table(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "wander_log.md"
            p.write_text(
                "# Wander Log\n\n"
                "| date_utc | question | overlap_max | similarity_max | seed_topic | attempts |\n"
                "|---|---|---:|---:|---|---:|\n"
                "| 2026-02-25T00:00:00Z | Question A? | 0.1 | 0.2 | active inference | 2 |\n",
                encoding="utf-8",
            )
            rows = parse_wander_log_questions(p, last_n=5)
            self.assertEqual(rows, ["Question A?"])

    def test_parse_wander_log_legacy_generated_question(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "wander_log.md"
            p.write_text(
                "## 2026-02-25 00:00\n\n"
                "Wandered: topic\n\n"
                "Generated question: Legacy Question?\n\n---\n",
                encoding="utf-8",
            )
            rows = parse_wander_log_questions(p, last_n=5)
            self.assertEqual(rows, ["Legacy Question?"])


if __name__ == "__main__":
    unittest.main()
