import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_SCRIPT = REPO_ROOT / "workspace" / "scripts" / "telegram_vector_store.py"
SEARCH_SCRIPT = REPO_ROOT / "workspace" / "scripts" / "search_telegram.py"


class SearchTelegramTests(unittest.TestCase):
    def _write_normalized(self, path: Path) -> None:
        rows = [
            {
                "hash": "search-a",
                "chat_id": "111",
                "chat_title": "c_lawd chat",
                "message_id": "1",
                "timestamp": "2026-02-20T10:00:00Z",
                "sender_name": "jeebs",
                "text": "Remember the openclaw 100 enhancements planning discussion.",
                "reply_to_message_id": None,
            },
            {
                "hash": "search-b",
                "chat_id": "111",
                "chat_title": "c_lawd chat",
                "message_id": "2",
                "timestamp": "2026-02-20T10:01:00Z",
                "sender_name": "c_lawd",
                "text": "We also reviewed vllm service health checks.",
                "reply_to_message_id": "1",
            },
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    def test_search_cli_returns_top_match(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            normalized = root / "normalized.jsonl"
            store_dir = root / "store"
            self._write_normalized(normalized)

            build_proc = subprocess.run(
                [
                    "python3",
                    str(STORE_SCRIPT),
                    "build",
                    "--normalized",
                    str(normalized),
                    "--store-dir",
                    str(store_dir),
                    "--backend",
                    "jsonl",
                    "--embedder",
                    "keyword_stub",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(build_proc.returncode, 0, build_proc.stdout + build_proc.stderr)

            search_proc = subprocess.run(
                [
                    "python3",
                    str(SEARCH_SCRIPT),
                    "100 enhancements planning",
                    "--store-dir",
                    str(store_dir),
                    "--topk",
                    "1",
                    "--json",
                ],
                cwd=str(REPO_ROOT),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(search_proc.returncode, 0, search_proc.stdout + search_proc.stderr)
            payload = json.loads(search_proc.stdout)
            self.assertEqual(len(payload), 1)
            self.assertIn("enhancements planning discussion", payload[0]["snippet"].lower())


if __name__ == "__main__":
    unittest.main()
