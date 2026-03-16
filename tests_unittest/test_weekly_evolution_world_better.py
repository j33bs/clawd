import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api import weekly_evolution  # noqa: E402


class WeeklyEvolutionWorldBetterTests(unittest.TestCase):
    def test_report_parser_ignores_non_weekly_markdown_and_reads_new_sections(self):
        with tempfile.TemporaryDirectory() as td:
            evolution_root = Path(td)
            weekly_path = evolution_root / "2026-W11.md"
            weekly_path.write_text(
                """# Weekly Evolution Report - 2026-W11

**Week of:** 2026-03-09
**Generated:** 2026-03-16T00:00:00Z

## Wins
- One packet everywhere.

## Regressions
- Timeline coverage incomplete.

## Top 3 Upgrades
1. Ship mission timeline.

## Human Benefit Signals
- Impact-ready mission tasks: 10/10 - complete.

## Guardrail Debt
- No material guardrail debt surfaced in this weekly sweep.

## Next Experiments
1. Implement shared packet schema.

## Notes
- Generated from Source.
""",
                encoding="utf-8",
            )
            (evolution_root / "source-world-better-roadmap.md").write_text("# Not a weekly report\n", encoding="utf-8")
            with mock.patch.object(weekly_evolution, "EVOLUTION_ROOT", evolution_root):
                summary = weekly_evolution.load_weekly_evolution_summary()

        self.assertEqual(summary["week_of"], "2026-03-09")
        self.assertEqual(summary["human_benefit_signals"][0], "Impact-ready mission tasks: 10/10 - complete.")
        self.assertEqual(summary["next_experiments"][0], "Implement shared packet schema.")
        self.assertTrue(summary["latest_report_path"].endswith("2026-W11.md"))


if __name__ == "__main__":
    unittest.main()
