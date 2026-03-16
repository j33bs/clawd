import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api import research_promotions, task_store  # noqa: E402
import app as source_ui_app  # noqa: E402


class ResearchPromotionTests(unittest.TestCase):
    def test_promote_research_item_creates_experiment_with_source_links(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tasks_path = root / 'tasks.json'
            tasks_path.write_text('[]\n', encoding='utf-8')
            research_path = root / 'research.jsonl'
            research_path.write_text(
                json.dumps(
                    {
                        'guild_id': 'g1',
                        'channel_id': 'c1',
                        'channel_name': 'dali-research',
                        'message_id': 'm-1',
                        'author_name': 'jeebs',
                        'role': 'user',
                        'created_at': '2026-03-12T00:01:00Z',
                        'content': 'investigate a smallest viable experiment for this research prompt',
                    }
                )
                + '\n',
                encoding='utf-8',
            )
            mission_path = root / 'source_mission.json'

            with mock.patch.object(task_store, 'SOURCE_MISSION_CONFIG_PATH', mission_path):
                result = research_promotions.promote_research_item(
                    {
                        'research_id': 'm-1',
                        'task_kind': 'experiment',
                        'title': 'Experiment: smallest viable prompt',
                        'assignee': 'dali',
                        'priority': 'high',
                    },
                    path=tasks_path,
                    research_path=research_path,
                )

            task = result['task']
            self.assertEqual(task['task_kind'], 'experiment')
            self.assertEqual(task['assignee'], 'dali')
            self.assertEqual(task['origin'], 'research_distill')
            self.assertEqual(task['research_item_id'], 'm-1')
            self.assertEqual(task['source_links'][0]['href'], '/api/research/items/m-1')
            self.assertEqual(task['source_refs'][0], 'discord:g1:c1:m-1')

    def test_list_research_items_surfaces_existing_promotions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tasks_path = root / 'tasks.json'
            tasks_path.write_text(
                json.dumps(
                    [
                        {
                            'id': 1001,
                            'title': 'Research follow-up',
                            'status': 'backlog',
                            'priority': 'high',
                            'assignee': 'dali',
                            'origin': 'research_distill',
                            'task_kind': 'task',
                            'research_item_id': 'm-2',
                            'source_links': [
                                {
                                    'id': 'm-2',
                                    'label': 'discord research · #dali-research',
                                    'href': '/api/research/items/m-2',
                                    'ref': 'discord:g1:c1:m-2',
                                }
                            ],
                        }
                    ],
                    indent=2,
                )
                + '\n',
                encoding='utf-8',
            )
            research_path = root / 'research.jsonl'
            research_path.write_text(
                json.dumps(
                    {
                        'guild_id': 'g1',
                        'channel_id': 'c1',
                        'channel_name': 'dali-research',
                        'message_id': 'm-2',
                        'author_name': 'jeebs',
                        'role': 'user',
                        'stored_at': '2026-03-12T00:02:00Z',
                        'content': 'second research prompt',
                    }
                )
                + '\n',
                encoding='utf-8',
            )
            items = research_promotions.list_research_items(tasks_path=tasks_path, research_path=research_path)
            self.assertEqual(items[0]['promotion_count'], 1)
            self.assertEqual(items[0]['promotions'][0]['task_id'], '1001')


class ResearchPromotionHandlerTests(unittest.TestCase):
    def test_promote_research_handler_returns_payload(self):
        state = source_ui_app.State()
        source_ui_app.SourceUIHandler._state = state
        handler = object.__new__(source_ui_app.SourceUIHandler)
        body = json.dumps({'research_id': 'm-9', 'assignee': 'dali'}).encode('utf-8')
        handler.headers = {'Content-Length': str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.send_json = mock.Mock()
        handler._load_tasks = mock.Mock(return_value=[])
        with mock.patch.object(
            source_ui_app,
            'task_store_promote_research_item',
            return_value={'ok': True, 'task': {'id': 1004, 'title': 'Promoted task'}},
        ):
            handler.promote_research_handler()

        handler.send_json.assert_called_once()
        payload = handler.send_json.call_args.args[0]
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['task']['id'], 1004)


if __name__ == '__main__':
    unittest.main()
