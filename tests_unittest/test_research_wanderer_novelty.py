import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from research_wanderer import evaluate_novelty, parse_wander_log_questions, select_question  # noqa: E402


class TestResearchWandererNovelty(unittest.TestCase):
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

    def test_parse_wander_log_table(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "wander_log.md"
            p.write_text(
                "# Wander Log\n\n| date_utc | question | overlap_max | similarity_max | seed_topic |\n|---|---|---:|---:|---|\n| 2026-02-25T00:00:00Z | Question A? | 0.1 | 0.2 | active inference |\n",
                encoding="utf-8",
            )
            rows = parse_wander_log_questions(p, last_n=5)
            self.assertEqual(rows, ["Question A?"])


if __name__ == "__main__":
    unittest.main()
