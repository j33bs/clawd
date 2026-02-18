import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti_cr.hivemind_bridge import hivemind_query, hivemind_store  # noqa: E402


class TestTactiCRHiveMindBridge(unittest.TestCase):
    @patch("tacti_cr.hivemind_bridge._memory_tool_path")
    @patch("tacti_cr.hivemind_bridge.subprocess.run")
    def test_hivemind_query_parses_json_results(self, mock_run, mock_tool_path):
        mock_tool_path.return_value = REPO_ROOT / "scripts" / "memory_tool.py"
        mock_proc = Mock(returncode=0)
        mock_proc.stdout = json.dumps(
            {
                "results": [
                    {
                        "kind": "fact",
                        "source": "manual",
                        "agent_scope": "main",
                        "score": 4,
                        "created_at": "2026-02-18T00:00:00+00:00",
                        "content": "routing note",
                        "metadata": {"x": 1},
                    }
                ]
            }
        )
        mock_run.return_value = mock_proc

        rows = hivemind_query("routing", "main", limit=2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].content, "routing note")

    @patch("tacti_cr.hivemind_bridge._memory_tool_path")
    @patch("tacti_cr.hivemind_bridge.subprocess.run")
    def test_hivemind_store_returns_true_on_stored(self, mock_run, mock_tool_path):
        mock_tool_path.return_value = REPO_ROOT / "scripts" / "memory_tool.py"
        mock_proc = Mock(returncode=0)
        mock_proc.stdout = json.dumps({"stored": True, "content_hash": "abc"})
        mock_run.return_value = mock_proc

        ok = hivemind_store(
            {
                "kind": "fact",
                "content": "ctx",
                "source": "tacti_cr.test",
                "agent_scope": "main",
            }
        )
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
