import unittest
from pathlib import Path
import sys
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api.relational_state import build_relational_prompt_lines, derive_response_style  # noqa: E402


class TestRelationalState(unittest.TestCase):
    def test_derive_response_style_prefers_listen_first_for_filler_risk(self):
        style = derive_response_style(
            {
                "pause_check": [{"fills_space": 0.82, "value_add": 0.21}],
                "session": {},
                "tacti": {},
                "di_alert": False,
            }
        )
        self.assertEqual(style["mode"], "listen_first")
        self.assertIn("filler risk", style["reason"].lower())

    def test_derive_response_style_uses_repair_for_low_attunement(self):
        style = derive_response_style(
            {
                "pause_check": [],
                "session": {"attunement_index": 0.25, "trust_score": 0.40},
                "tacti": {},
                "di_alert": False,
            }
        )
        self.assertEqual(style["mode"], "repair")
        self.assertTrue(any("acknowledge friction" in row.lower() for row in style["directives"]))

    def test_build_relational_prompt_lines_merges_harness_directives(self):
        payload = {
            "signal_count": 2,
            "response_style": {
                "mode": "de_escalate",
                "reason": "Arousal is elevated.",
                "directives": ["Use short sentences."],
            },
        }
        with mock.patch("api.relational_state.load_relational_state", return_value=payload):
            lines = build_relational_prompt_lines(
                harness={"relational_modes": {"de_escalate": ["Give one clean next step."]}},
                limit=5,
            )
        self.assertIn("- Mode: de_escalate.", lines)
        self.assertIn("- Reason: Arousal is elevated.", lines)
        self.assertIn("- Give one clean next step.", lines)


if __name__ == "__main__":
    unittest.main()
