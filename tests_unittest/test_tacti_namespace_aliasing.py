import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class TestTactiNamespaceAliasing(unittest.TestCase):
    def test_arousal_alias_functional_equivalence(self):
        import workspace.tacti.arousal as canonical
        import workspace.tacti_cr.arousal as legacy

        text = "must fail-closed under strict constraints with traceback and context budget"
        canonical_state = canonical.detect_arousal(text)
        legacy_state = legacy.detect_arousal(text)
        self.assertEqual(canonical_state.level, legacy_state.level)
        self.assertEqual(canonical_state.score, legacy_state.score)
        self.assertEqual(canonical_state.reasons, legacy_state.reasons)

        canonical_plan = canonical.get_compute_allocation(canonical_state)
        legacy_plan = legacy.get_compute_allocation(legacy_state)
        self.assertEqual(asdict(canonical_plan), asdict(legacy_plan))

    def test_events_alias_shares_persistence_target_contract(self):
        import workspace.tacti.events as canonical_events
        import workspace.tacti_cr.events as legacy_events

        self.assertEqual(str(canonical_events.DEFAULT_PATH), str(legacy_events.DEFAULT_PATH))

        with tempfile.TemporaryDirectory() as td:
            sink = Path(td) / "events.jsonl"
            old_canonical = canonical_events.DEFAULT_PATH
            old_legacy = legacy_events.DEFAULT_PATH
            canonical_events.DEFAULT_PATH = sink
            legacy_events.DEFAULT_PATH = sink
            try:
                canonical_events.emit("tacti.alias.canonical", {"path": "canonical"}, session_id="s1")
                legacy_events.emit("tacti.alias.legacy", {"path": "legacy"}, session_id="s1")
            finally:
                canonical_events.DEFAULT_PATH = old_canonical
                legacy_events.DEFAULT_PATH = old_legacy

            rows = [json.loads(line) for line in sink.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(2, len(rows))
            self.assertEqual("tacti.alias.canonical", rows[0]["type"])
            self.assertEqual("tacti.alias.legacy", rows[1]["type"])


if __name__ == "__main__":
    unittest.main()
