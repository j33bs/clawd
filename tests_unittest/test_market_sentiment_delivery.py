import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace.market_sentiment.delivery import deliver_snapshot


class _CompletedProcess:
    def __init__(self, returncode=0, stderr=b""):
        self.returncode = returncode
        self.stderr = stderr


class TestMarketSentimentDelivery(unittest.TestCase):
    def test_disabled_delivery_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "snapshot.json"
            local_path.write_text("{}", encoding="utf-8")
            result = deliver_snapshot(local_path, {"delivery": {"enabled": False}})
        self.assertEqual(result.status, "skipped")

    @patch("workspace.market_sentiment.delivery.subprocess.run")
    def test_ssh_push_writes_remote_temp_and_renames(self, run_mock):
        run_mock.return_value = _CompletedProcess(returncode=0)
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "snapshot.json"
            local_path.write_text('{"status":"ok"}\n', encoding="utf-8")
            result = deliver_snapshot(
                local_path,
                {
                    "delivery": {
                        "enabled": True,
                        "mode": "ssh_push",
                        "host": "100.113.160.1",
                        "user": "jeebs",
                        "disable_ssh_config": True,
                        "remote_path": "/home/jeebs/src/clawd/workspace/state/external/macbook_sentiment.json",
                        "timeout_seconds": 15,
                        "connect_timeout_seconds": 5,
                    }
                },
            )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.target, "jeebs@100.113.160.1:/home/jeebs/src/clawd/workspace/state/external/macbook_sentiment.json")
        self.assertEqual(run_mock.call_count, 1)
        args, kwargs = run_mock.call_args
        self.assertEqual(args[0][0], "ssh")
        self.assertIn("-F", args[0])
        self.assertIn("/dev/null", args[0])
        self.assertIn("jeebs@100.113.160.1", args[0])
        self.assertIn("mkdir -p /home/jeebs/src/clawd/workspace/state/external", args[0][-1])
        self.assertIn("cat > /home/jeebs/src/clawd/workspace/state/external/macbook_sentiment.json.tmp.", args[0][-1])
        self.assertIn("mv /home/jeebs/src/clawd/workspace/state/external/macbook_sentiment.json.tmp.", args[0][-1])
        self.assertEqual(kwargs["input"], b'{"status":"ok"}\n')


if __name__ == "__main__":
    unittest.main()
