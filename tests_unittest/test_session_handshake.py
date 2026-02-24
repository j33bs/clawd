import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace"))

from memory.relationship_tracker import load_state as load_relationship_state  # noqa: E402
from memory.session_handshake import close_session_handshake, load_session_handshake  # noqa: E402


class TestSessionHandshake(unittest.TestCase):
    def test_open_and_close_persist_artifacts_and_relationship_state(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            summary = repo_root / "workspace" / "teamchat" / "summaries" / "session-a.md"
            summary.parent.mkdir(parents=True, exist_ok=True)
            summary.write_text("# Summary\n\nok\n", encoding="utf-8")

            with patch("memory.session_handshake.tacti_emit") as mock_emit:
                opened = load_session_handshake(
                    repo_root=repo_root,
                    session_id="session-a",
                    summary_file=summary,
                    outstanding_threads=["todo-1"],
                    source="teamchat",
                )
                closed = close_session_handshake(
                    repo_root=repo_root,
                    session_id="session-a",
                    summary_file=summary,
                    status="accepted",
                    outstanding_threads=[],
                    source="teamchat",
                )

            self.assertEqual("handshake_loaded", opened["type"])
            self.assertEqual("session_closed", closed["type"])
            self.assertTrue(Path(opened["artifact_path"]).exists())
            self.assertTrue(Path(closed["artifact_path"]).exists())
            self.assertEqual(2, mock_emit.call_count)

            rel = load_relationship_state(repo_root=repo_root)
            row = rel["sessions"]["session-a"]
            self.assertEqual(1, row["open_count"])
            self.assertEqual(1, row["close_count"])
            self.assertEqual(0, row["unresolved_threads"])
            self.assertTrue(row["last_summary_ref"].endswith("workspace/teamchat/summaries/session-a.md"))


if __name__ == "__main__":
    unittest.main()
