import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "telegram_refresh.py"
FIXTURE_PATH = REPO_ROOT / "workspace" / "fixtures" / "telegram_export_min.json"


def load_module():
    script_dir = str(SCRIPT_PATH.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("telegram_refresh", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TelegramRefreshTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_skips_when_no_exports_or_normalized_history(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            summary = self.mod.refresh_telegram_memory(
                export_root=root / "exports",
                normalized_path=root / "normalized" / "messages.jsonl",
                store_dir=root / "store",
                embedder_name="keyword_stub",
                backend="jsonl",
            )
            self.assertEqual(summary["status"], "skipped")

    def test_refreshes_from_latest_export_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            export_dir = root / "exports" / "20260311"
            export_dir.mkdir(parents=True)
            (export_dir / "result.json").write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            summary = self.mod.refresh_telegram_memory(
                export_root=root / "exports",
                normalized_path=root / "normalized" / "messages.jsonl",
                store_dir=root / "store",
                embedder_name="keyword_stub",
                backend="jsonl",
            )
            self.assertEqual(summary["status"], "ok")
            self.assertGreaterEqual(summary["ingest"]["files_scanned"], 1)
            self.assertGreater(summary["build"]["count"], 0)

    def test_rebuilds_from_existing_normalized_history(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            normalized = root / "normalized" / "messages.jsonl"
            normalized.parent.mkdir(parents=True, exist_ok=True)
            rows = [
                {
                    "hash": "refresh-a",
                    "chat_id": "111",
                    "chat_title": "chat",
                    "message_id": "1",
                    "timestamp": "2026-03-11T00:00:00Z",
                    "sender_name": "jeebs",
                    "text": "telegram refresh rebuild path",
                    "reply_to_message_id": None,
                }
            ]
            with normalized.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=True) + "\n")
            summary = self.mod.refresh_telegram_memory(
                export_root=root / "exports",
                normalized_path=normalized,
                store_dir=root / "store",
                embedder_name="keyword_stub",
                backend="jsonl",
            )
            self.assertEqual(summary["status"], "rebuilt_from_existing_normalized")
            self.assertEqual(summary["build"]["count"], 1)

    def test_discovers_export_from_fallback_search_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fallback_root = root / "Downloads"
            export_dir = fallback_root / "Telegram Desktop" / "ChatExport_1"
            export_dir.mkdir(parents=True)
            (export_dir / "result.json").write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

            discovered = self.mod.discover_latest_export_path(
                root / "missing_primary",
                search_roots=[fallback_root],
            )

            self.assertEqual(discovered.resolve(), export_dir.resolve())

    def test_ignores_repo_copies_while_searching_fallback_roots(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fallback_root = root / "Downloads"
            repo_export = fallback_root / "clawd-main"
            (repo_export / ".git").mkdir(parents=True)
            (repo_export / "workspace" / "fixtures").mkdir(parents=True)
            (repo_export / "workspace" / "fixtures" / "result.json").write_text(
                FIXTURE_PATH.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            real_export = fallback_root / "Telegram Desktop" / "ChatExport_2"
            real_export.mkdir(parents=True)
            (real_export / "result.json").write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

            discovered = self.mod.discover_latest_export_path(
                root / "missing_primary",
                search_roots=[fallback_root],
            )

            self.assertEqual(discovered.resolve(), real_export.resolve())


if __name__ == "__main__":
    unittest.main()
