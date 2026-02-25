import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT / "workspace" / "knowledge_base") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "knowledge_base"))

import kb  # noqa: E402
from graph.store import KnowledgeGraphStore, _allow_write, _is_protected_target  # noqa: E402


class TestQuiesceProtectsTrackedState(unittest.TestCase):
    def test_protected_matcher_covers_required_targets(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            targets = [
                root / "MEMORY.md",
                root / "workspace" / "knowledge_base" / "data" / "entities.jsonl",
                root / "workspace" / "knowledge_base" / "data" / "last_sync.txt",
                root / "workspace" / "state" / "tacti_cr" / "events.jsonl",
            ]
            for target in targets:
                self.assertTrue(_is_protected_target(target), msg=f"expected protected target: {target}")

    def test_quiesce_blocks_entities_write(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "workspace" / "knowledge_base" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            entities_path = data_dir / "entities.jsonl"
            buf = io.StringIO()
            with patch.dict(os.environ, {"OPENCLAW_QUIESCE": "1"}, clear=False):
                with redirect_stdout(buf):
                    store = KnowledgeGraphStore(data_dir)
                    store.add_entity(
                        name="test",
                        entity_type="fact",
                        content="payload",
                        source="test",
                        metadata={"x": 1},
                    )
            self.assertIn("QUIESCED: skipping write to", buf.getvalue())
            if entities_path.exists():
                self.assertEqual(entities_path.read_text(encoding="utf-8"), "")

    def test_quiesce_blocks_last_sync_write(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "workspace" / "knowledge_base" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            marker = data_dir / "last_sync.txt"
            buf = io.StringIO()
            with patch.dict(os.environ, {"OPENCLAW_QUIESCE": "1"}, clear=False):
                with redirect_stdout(buf):
                    wrote = kb._write_last_sync_marker(data_dir)
            self.assertFalse(wrote)
            self.assertFalse(marker.exists())
            self.assertIn("QUIESCED: skipping write to", buf.getvalue())

    def test_last_sync_write_allowed_when_not_quiesced(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "workspace" / "knowledge_base" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            marker = data_dir / "last_sync.txt"
            with patch.dict(os.environ, {"OPENCLAW_QUIESCE": "0"}, clear=False):
                wrote = kb._write_last_sync_marker(data_dir)
            self.assertTrue(wrote)
            self.assertTrue(marker.exists())
            self.assertTrue(marker.read_text(encoding="utf-8").strip())

    def test_quiesce_blocks_events_path_in_guard(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "workspace" / "state" / "tacti_cr" / "events.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"OPENCLAW_QUIESCE": "1"}, clear=False):
                with redirect_stdout(buf):
                    allowed = _allow_write(path)
            self.assertFalse(allowed)
            self.assertIn("QUIESCED: skipping write to", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
