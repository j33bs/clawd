#!/usr/bin/env python3
"""
Source UI - OpenClaw System Management Dashboard
A beautiful, functional control center for OpenClaw.
"""

import json
import os
import sys
import argparse
import logging
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import socketserver

try:
    from api.trails import trails_heatmap_payload
except Exception:  # pragma: no cover
    trails_heatmap_payload = None

try:
    from api.portfolio import portfolio_payload
except Exception:  # pragma: no cover
    portfolio_payload = None

try:
    from api.task_store import (
        archive_task as task_store_archive_task,
        create_task as task_store_create_task,
        delete_task as task_store_delete_task,
        load_all_tasks as task_store_load_all_tasks,
        load_archived_tasks as task_store_load_archived_tasks,
        load_runtime_tasks as task_store_load_runtime_tasks,
        load_tasks as task_store_load_tasks,
        update_task as task_store_update_task,
    )
except Exception:  # pragma: no cover
    task_store_archive_task = None
    task_store_create_task = None
    task_store_delete_task = None
    task_store_load_all_tasks = None
    task_store_load_archived_tasks = None
    task_store_load_runtime_tasks = None
    task_store_load_tasks = None
    task_store_update_task = None

try:
    from api.user_inference import (
        load_user_inferences as user_inference_load_all,
        update_user_inference as user_inference_update,
    )
except Exception:  # pragma: no cover
    user_inference_load_all = None
    user_inference_update = None

try:
    from api.display_mode import (
        load_display_mode_status as display_mode_load_status,
        toggle_display_mode as display_mode_toggle,
    )
except Exception:  # pragma: no cover
    display_mode_load_status = None
    display_mode_toggle = None

try:
    from api.research_promotions import (
        get_research_item as task_store_get_research_item,
        list_research_items as task_store_list_research_items,
        promote_research_item as task_store_promote_research_item,
    )
except Exception:  # pragma: no cover
    task_store_get_research_item = None
    task_store_list_research_items = None
    task_store_promote_research_item = None

try:
    from api.relational_state import load_relational_state
except Exception:  # pragma: no cover
    load_relational_state = None

try:
    from api.deliberation_store import (
        add_contribution as deliberation_add_contribution,
        add_synthesis as deliberation_add_synthesis,
        create_deliberation as deliberation_create,
        get_deliberation as deliberation_get,
        list_deliberations as deliberation_list,
    )
except Exception:  # pragma: no cover
    deliberation_add_contribution = None
    deliberation_add_synthesis = None
    deliberation_create = None
    deliberation_get = None
    deliberation_list = None

try:
    from api.weekly_evolution import (
        generate_weekly_evolution,
        load_weekly_evolution_summary,
    )
except Exception:  # pragma: no cover
    generate_weekly_evolution = None
    load_weekly_evolution_summary = None

try:
    from api.boundary_state import build_command_receipt_boundary
except Exception:  # pragma: no cover
    build_command_receipt_boundary = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('source-ui')

SOURCE_UI_ROOT = Path(__file__).resolve().parent
STATE_ROOT = SOURCE_UI_ROOT / "state"
COMMAND_HISTORY_PATH = STATE_ROOT / "command_history.json"
COMMAND_RECEIPTS_PATH = STATE_ROOT / "command_receipts.json"
AGENT_CONTROLS_PATH = STATE_ROOT / "agent_controls.json"


def source_contract_payload() -> dict[str, Any]:
    return {
        "name": "source-ui",
        "statement": "Source UI is the operator surface and runtime mirror for Source.",
        "principles": [
            "Read structured APIs rather than scraping the DOM.",
            "Treat runtime tasks as read-only observations unless you own the source session.",
            "Write canonical editable tasks through /api/tasks only.",
            "Use /api/runtime-tasks for live session visibility across nodes.",
        ],
        "endpoints": {
            "status": "/api/status",
            "portfolio": "/api/portfolio",
            "world_better": "/api/world-better",
            "tasks": "/api/tasks",
            "runtime_tasks": "/api/runtime-tasks",
            "command_history": "/api/commands/history",
            "command_receipts": "/api/commands/receipts",
        },
        "task_contract": {
            "editable_local_tasks": {
                "origin": "dashboard",
                "read_only": False,
            },
            "runtime_tasks": {
                "origins": ["runtime-session", "runtime-subagent", "runtime-remote"],
                "read_only": True,
                "fields": ["node_id", "node_label", "runtime_source", "runtime_source_label", "session_id"],
            },
        },
        "cross_node": {
            "expected_remote_endpoint": "http://<tailscale-ip>:18990/api/runtime-tasks",
            "discovery_file": "workspace/source-ui/config/runtime_task_sources.json",
        },
    }


def _read_json_file(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _decorate_command_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    row = dict(receipt)
    if build_command_receipt_boundary is not None:
        row["boundary"] = build_command_receipt_boundary(row)
    return row


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class Config:
    """Source UI configuration."""
    host: str = "127.0.0.1"
    port: int = 18990
    gateway_url: str = "http://127.0.0.1:18789"
    gateway_token: Optional[str] = None
    static_dir: str = ""
    auto_refresh_interval: int = 10
    log_level: str = "INFO"
    
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> 'Config':
        gateway_token = args.token or os.environ.get('OPENCLAW_TOKEN')
        
        static_dir = args.static_dir
        if not static_dir:
            static_dir = str(Path(__file__).parent / "static")
        
        return cls(
            host=args.host,
            port=args.port,
            gateway_url=args.gateway or os.environ.get('GATEWAY_URL', 'http://127.0.0.1:18789'),
            gateway_token=gateway_token,
            static_dir=static_dir,
            auto_refresh_interval=args.refresh,
            log_level=args.log_level
        )


# ============================================================================
# State Management
# ============================================================================

class State:
    """Application state management."""
    
    def __init__(self):
        self.agents: list[dict] = []
        self.tasks: list[dict] = []
        self.scheduled_jobs: list[dict] = []
        self.health_metrics: dict = {}
        self.components: list[dict] = []
        self.notifications: list[dict] = []
        self.logs: list[dict] = []
        self.command_events: list[dict] = self._load_command_events()
        self.command_receipts: list[dict] = self._load_command_receipts()
        self.agent_controls: dict[str, dict[str, Any]] = self._load_agent_controls()
        self.command_lock = threading.Lock()
        self.gateway_connected: bool = False
        self.last_update: Optional[datetime] = None
        
    def to_dict(self) -> dict:
        return {
            'agents': self.agents,
            'tasks': self.tasks,
            'scheduled_jobs': self.scheduled_jobs,
            'health_metrics': self.health_metrics,
            'components': self.components,
            'notifications': self.notifications,
            'logs': self.logs,
            'command_events': self.command_events,
            'command_receipts': self.command_receipts,
            'agent_controls': self.agent_controls,
            'gateway_connected': self.gateway_connected,
            'last_update': self.last_update.isoformat() if self.last_update else None
        }

    def _load_command_events(self) -> list[dict]:
        payload = _read_json_file(COMMAND_HISTORY_PATH)
        if not isinstance(payload, list):
            return []
        rows: list[dict] = []
        for item in payload[:20]:
            if isinstance(item, dict):
                rows.append(item)
        return rows

    def persist_command_events(self) -> None:
        _write_json_atomic(COMMAND_HISTORY_PATH, self.command_events[:20])

    def _load_command_receipts(self) -> list[dict]:
        payload = _read_json_file(COMMAND_RECEIPTS_PATH)
        if not isinstance(payload, list):
            return []
        rows: list[dict] = []
        for item in payload[:50]:
            if isinstance(item, dict):
                rows.append(_decorate_command_receipt(item))
        return rows

    def persist_command_receipts(self) -> None:
        _write_json_atomic(COMMAND_RECEIPTS_PATH, self.command_receipts[:50])

    def _load_agent_controls(self) -> dict[str, dict[str, Any]]:
        payload = _read_json_file(AGENT_CONTROLS_PATH)
        if not isinstance(payload, dict):
            return {}
        return {str(key): value for key, value in payload.items() if isinstance(value, dict)}

    def persist_agent_controls(self) -> None:
        _write_json_atomic(AGENT_CONTROLS_PATH, self.agent_controls)


# ============================================================================
# Demo Data Generator
# ============================================================================

class DemoDataGenerator:
    """Generate demo data."""
    
    @staticmethod
    def generate_agents() -> list[dict]:
        return [
            {'id': 'planner', 'name': 'Planner', 'model': 'MiniMax-M2.5', 'status': 'idle', 'tasks_completed': 12, 'cycles': 156},
            {'id': 'coder', 'name': 'Coder', 'model': 'Codex', 'status': 'working', 'task': 'Implementing Source UI', 'progress': 65, 'tasks_completed': 24, 'cycles': 89},
            {'id': 'health', 'name': 'Health Monitor', 'model': 'MiniMax-M2.5', 'status': 'idle', 'tasks_completed': 8, 'cycles': 24},
            {'id': 'memory', 'name': 'Memory Agent', 'model': 'MiniMax-M2.5', 'status': 'working', 'task': 'Indexing memories', 'progress': 30, 'tasks_completed': 15, 'cycles': 42}
        ]
    
    @staticmethod
    def generate_tasks() -> list[dict]:
        now = datetime.now()
        return [
            {'id': 1, 'title': 'Implement task drag-and-drop', 'status': 'in_progress', 'priority': 'high', 'assignee': 'coder', 'created_at': now.isoformat()},
            {'id': 2, 'title': 'Add WebSocket support', 'status': 'backlog', 'priority': 'high', 'assignee': 'coder', 'created_at': now.isoformat()},
            {'id': 3, 'title': 'Write API integration tests', 'status': 'backlog', 'priority': 'medium', 'assignee': 'coder', 'created_at': now.isoformat()},
            {'id': 4, 'title': 'Design notification system', 'status': 'review', 'priority': 'medium', 'assignee': 'planner', 'created_at': now.isoformat()},
            {'id': 5, 'title': 'Fix memory leak in worker', 'status': 'done', 'priority': 'high', 'assignee': 'coder', 'created_at': now.isoformat()},
            {'id': 6, 'title': 'Update documentation', 'status': 'backlog', 'priority': 'low', 'assignee': 'planner', 'created_at': now.isoformat()}
        ]
    
    @staticmethod
    def generate_scheduled_jobs() -> list[dict]:
        return [
            {'id': 1, 'name': 'Daily Health Check', 'cron': '0 9 * * *', 'next_run': '9:00 AM', 'enabled': True},
            {'id': 2, 'name': 'Security Audit', 'cron': '0 9 * * 1', 'next_run': 'Mon 9:00 AM', 'enabled': True},
            {'id': 3, 'name': 'Memory Cleanup', 'cron': '0 0 * * *', 'next_run': '12:00 AM', 'enabled': True},
            {'id': 4, 'name': 'Git Auto-commit', 'cron': '*/15 * * * *', 'next_run': 'Every 15min', 'enabled': True}
        ]
    
    @staticmethod
    def generate_components() -> list[dict]:
        return [
            {'id': 'gateway', 'name': 'Gateway', 'status': 'healthy', 'details': 'Running on port 18789'},
            {'id': 'vllm', 'name': 'VLLM', 'status': 'healthy', 'details': 'Online at localhost:8001'},
            {'id': 'telegram', 'name': 'Telegram', 'status': 'healthy', 'details': 'Connected'},
            {'id': 'memory', 'name': 'Memory', 'status': 'warning', 'details': 'Low available'},
            {'id': 'database', 'name': 'Database', 'status': 'healthy', 'details': 'Connected'},
            {'id': 'scheduler', 'name': 'Scheduler', 'status': 'healthy', 'details': '4 jobs active'}
        ]
    
    @staticmethod
    def generate_logs() -> list[dict]:
        now = datetime.now()
        return [
            {'level': 'info', 'message': 'Gateway started successfully', 'timestamp': now.isoformat()},
            {'level': 'info', 'message': 'Connected to VLLM at localhost:8001', 'timestamp': (now - timedelta(minutes=1)).isoformat()},
            {'level': 'warn', 'message': 'Memory usage high: 78%', 'timestamp': (now - timedelta(minutes=2)).isoformat()},
            {'level': 'info', 'message': 'Telegram bot authenticated', 'timestamp': (now - timedelta(minutes=3)).isoformat()},
            {'level': 'error', 'message': 'Failed to connect to external API', 'timestamp': (now - timedelta(minutes=4)).isoformat()}
        ]
    
    @staticmethod
    def generate_health_metrics() -> dict:
        import random
        return {
            'cpu': random.randint(20, 60),
            'memory': random.randint(40, 80),
            'disk': random.randint(30, 60),
            'gpu': random.randint(20, 70)
        }


# ============================================================================
# Request Handler
# ============================================================================

class SourceUIHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for Source UI."""
    
    # Class-level state and config
    _state = None
    _config = None
    
    def __init__(self, *args, **kwargs):
        self.demo = DemoDataGenerator()
        # Initialize demo data
        if self._state and not self._state.agents:
            self._state.agents = self.demo.generate_agents()
            self._state.tasks = self.demo.generate_tasks()
            self._state.scheduled_jobs = self.demo.generate_scheduled_jobs()
            self._state.components = self.demo.generate_components()
            self._state.logs = self.demo.generate_logs()
            self._state.health_metrics = self.demo.generate_health_metrics()
        
        super().__init__(*args, **kwargs)
    
    @property
    def state(self):
        return self._state
    
    @property
    def config(self):
        return self._config
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        # API endpoints
        if parsed.path.startswith('/api/'):
            self.handle_api(parsed)
            return
        
        # Root - serve index.html
        if self.path in ['/', '/index.html', '/ui', '/ui/']:
            self.serve_file('index.html', 'text/html')
            return
        
        # Static files
        if parsed.path.startswith('/static/'):
            self.serve_static(parsed.path[8:])
            return
        
        # Default to index
        self.serve_file('index.html', 'text/html')
    
    def do_POST(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/api/tasks':
            self.create_task()
        elif parsed.path.startswith('/api/agents/'):
            parts = parsed.path.split('/')
            if len(parts) >= 5:
                self.control_agent(parts[3], parts[4])
            else:
                self.send_error(404)
        elif parsed.path == '/api/refresh':
            self.refresh_data()
        elif parsed.path == '/api/health/check':
            self.run_health_check()
        elif parsed.path == '/api/gateway/restart':
            self.restart_gateway()
        elif parsed.path == '/api/commands':
            self.execute_command_deck()
        elif parsed.path == '/api/display-mode/toggle':
            self.toggle_display_mode_handler()
        elif parsed.path == '/api/research/promote':
            self.promote_research_handler()
        elif parsed.path == '/api/deliberations':
            self.create_deliberation_handler()
        elif parsed.path.startswith('/api/deliberations/') and parsed.path.endswith('/contributions'):
            deliberation_id = parsed.path.split('/')[-2]
            self.add_deliberation_contribution_handler(deliberation_id)
        elif parsed.path.startswith('/api/deliberations/') and parsed.path.endswith('/synthesis'):
            deliberation_id = parsed.path.split('/')[-2]
            self.add_deliberation_synthesis_handler(deliberation_id)
        elif parsed.path == '/api/evolution/generate':
            self.generate_weekly_evolution_handler()
        elif parsed.path.startswith('/api/tasks/') and parsed.path.endswith('/review'):
            task_id = parsed.path.split('/')[-2]
            self.review_task_handler(task_id)
        elif parsed.path.startswith('/api/tasks/') and parsed.path.endswith('/archive'):
            task_id = parsed.path.split('/')[-2]
            self.archive_task_handler(task_id)
        else:
            self.send_error(404)
    
    def do_PATCH(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/user-inferences/'):
            inference_id = parsed.path.split('/')[-1]
            self.update_user_inference_handler(inference_id)
        elif parsed.path.startswith('/api/tasks/'):
            task_id = parsed.path.split('/')[-1]
            self.update_task(task_id)
        elif parsed.path.startswith('/api/symbiote/enhancement/'):
            eid = parsed.path.split('/')[-1]
            self.update_symbiote_enhancement(eid)
        else:
            self.send_error(404)
    
    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/tasks/'):
            task_id = parsed.path.split('/')[-1]
            self.delete_task(task_id)
        else:
            self.send_error(404)
    
    def handle_api(self, parsed):
        """Handle API requests."""
        path = parsed.path[5:]  # Remove /api/
        
        if path == 'status':
            self.state.agents = self._load_agents()
            self.state.tasks = self._load_tasks()
            self.state.health_metrics = self._load_live_health_metrics()
            self.state.components = self._load_live_components()
            self.state.last_update = datetime.now()
            self.state.gateway_connected = any(
                str(component.get("id")) == "gateway" and str(component.get("status")) == "healthy"
                for component in self.state.components
            )
            data = {
                'status': 'ok',
                'agents': self.state.agents,
                'tasks': self.state.tasks,
                'scheduled_jobs': self.state.scheduled_jobs,
                'health_metrics': self.state.health_metrics,
                'components': self.state.components,
                'notifications': self.state.notifications,
                'logs': self.state.logs,
                'recent_commands': self.state.command_events[:10],
                'recent_receipts': self.state.command_receipts[:10],
                'gateway_connected': self.state.gateway_connected,
                'last_update': self.state.last_update.isoformat() if self.state.last_update else None,
            }
        elif path == 'agents':
            data = self._load_agents()
        elif path.startswith('agents/'):
            agent_id = path.split('/')[-1]
            data = next((row for row in self._load_agents() if str(row.get('id')) == agent_id), {'error': 'Not found'})
        elif path == 'tasks':
            data = self._load_tasks()
        elif path == 'runtime-tasks':
            data = self._load_runtime_tasks()
        elif path == 'schedule':
            data = self.state.scheduled_jobs
        elif path == 'health':
            data = self.state.health_metrics
        elif path == 'logs':
            data = self.state.logs
        elif path == 'commands/history':
            data = self.state.command_events[:20]
        elif path == 'commands/receipts':
            data = self.state.command_receipts[:20]
        elif path == 'portfolio':
            if portfolio_payload is None:
                data = {'error': 'portfolio_unavailable'}
            else:
                data = portfolio_payload()
        elif path == 'world-better':
            if portfolio_payload is None:
                data = {'error': 'portfolio_unavailable'}
            else:
                data = (portfolio_payload() or {}).get('world_better', {})
        elif path == 'display-mode':
            data = self.get_display_mode_data()
        elif path == 'research/items':
            data = self.get_research_items_data()
        elif path.startswith('research/items/'):
            research_id = path.partition('research/items/')[2]
            if task_store_get_research_item is None:
                data = {'error': 'research_unavailable'}
            else:
                data = task_store_get_research_item(research_id, tasks=self._load_tasks()) or {'error': 'Not found'}
        elif path == 'user-inferences':
            if user_inference_load_all is None:
                data = {'error': 'user_inference_unavailable'}
            else:
                data = user_inference_load_all()
        elif path == 'deliberations':
            if deliberation_list is None:
                data = {'error': 'deliberation_unavailable'}
            else:
                data = deliberation_list(limit=8)
        elif path.startswith('deliberations/'):
            deliberation_id = path.partition('deliberations/')[2]
            if deliberation_get is None:
                data = {'error': 'deliberation_unavailable'}
            else:
                data = deliberation_get(deliberation_id) or {'error': 'Not found'}
        elif path == 'evolution/latest':
            if load_weekly_evolution_summary is None:
                data = {'error': 'weekly_evolution_unavailable'}
            else:
                data = load_weekly_evolution_summary()
        elif path == 'source-contract':
            data = source_contract_payload()
        elif path == 'trails/heatmap':
            if trails_heatmap_payload is None:
                data = {'error': 'trails_heatmap_unavailable'}
            else:
                repo_root = Path(__file__).resolve().parents[2]
                data = trails_heatmap_payload(repo_root, top_n=20)
        elif path.startswith('state/valence/'):
            # Serve valence state files
            agent = path.split('/')[-1].replace('.json', '')
            repo_root = Path(__file__).resolve().parents[2]
            valence_file = repo_root / 'workspace' / 'state' / 'valence' / f'{agent}.json'
            if valence_file.exists():
                data = json.loads(valence_file.read_text())
            else:
                data = {'valence': 0.0, 'agent': agent}
        elif path == 'symbiote':
            data = self.symbiote_data()
        elif path == 'tasks/archived':
            data = self.get_archived_tasks_data()
        elif path == 'source/phi':
            data = self._source_phi_data()
        elif path == 'source/coordination-feed':
            data = self._source_coordination_feed()
        elif path == 'source/relational':
            data = self._source_relational_data()
        else:
            data = {'error': 'Not found'}
        
        self.send_json(data)

    def _read_json_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get('Content-Length', 0))
        except Exception:
            length = 0
        if length <= 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}
    
    def create_task(self):
        """Create a new task."""
        try:
            data = self._read_json_body()

            if task_store_create_task is None:
                raise RuntimeError('task_store_unavailable')

            task = task_store_create_task(data)
            self.state.tasks = self._load_tasks()
            self.send_json(task)
        except Exception as e:
            self.send_json({'error': str(e)}, status=400)
    
    def update_task(self, task_id):
        """Update a task."""
        try:
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length)) if length > 0 else {}

            if task_store_update_task is None:
                raise RuntimeError('task_store_unavailable')

            task = task_store_update_task(task_id, data)
            if task is None:
                self.send_json({'error': 'Task not found'}, status=404)
                return
            self.state.tasks = self._load_tasks()
            self.send_json(task)
        except Exception as e:
            self.send_json({'error': str(e)}, status=400)

    def update_user_inference_handler(self, inference_id):
        """Update review state for a durable user inference."""
        try:
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length)) if length > 0 else {}

            if user_inference_update is None:
                raise RuntimeError('user_inference_unavailable')

            row = user_inference_update(inference_id, data, reviewer='source-ui')
            if row is None:
                self.send_json({'error': 'Inference not found'}, status=404)
                return
            self.state.tasks = self._load_tasks()
            self.send_json(row)
        except Exception as e:
            self.send_json({'error': str(e)}, status=400)
    
    def delete_task(self, task_id):
        """Delete a task."""
        if task_store_delete_task is None:
            self.send_json({'error': 'task_store_unavailable'}, status=400)
            return
        deleted = task_store_delete_task(task_id)
        if not deleted:
            self.send_json({'error': 'Task not found'}, status=404)
            return
        self.state.tasks = self._load_tasks()
        self.send_json({'success': True})

    def review_task_handler(self, task_id):
        """Review a task: verify intent adherence and alignment, then approve or request changes."""
        if task_store_update_task is None:
            self.send_json({'error': 'task_store_unavailable'}, status=400)
            return

        body = self._read_json_body()
        approved = bool(body.get('approved', False))
        reviewer_notes = str(body.get('notes', '') or '')

        task = next((row for row in self._load_tasks() if str(row.get('id')) == str(task_id)), None)
        if task is None:
            self.send_json({'error': 'Task not found'}, status=404)
            return

        if str(task.get('status') or '') != 'review':
            self.send_json({'error': f"Task is not in review status (current: {task.get('status')})"}, status=400)
            return

        updates = {
            'status': 'done' if approved else 'in_progress',
            'reviewer_notes': reviewer_notes,
            'status_reason': reviewer_notes or (
                'Intent verified and aligned with Source Mission'
                if approved
                else 'Changes requested by operator'
            ),
        }
        if approved:
            updates['reviewed_by'] = 'operator'

        updated = task_store_update_task(task_id, updates)
        if updated is None:
            self.send_json({'error': 'Task not found'}, status=404)
            return
        self.state.tasks = self._load_tasks()
        self.send_json({'success': True, 'task': updated, 'action': 'approved' if approved else 'changes_requested'})

    def create_deliberation_handler(self):
        if deliberation_create is None:
            self.send_json({'error': 'deliberation_unavailable'}, status=400)
            return
        body = self._read_json_body()
        try:
            row = deliberation_create(
                title=str(body.get('title') or '').strip(),
                prompt=str(body.get('prompt') or '').strip(),
                roles=body.get('roles'),
                participants=body.get('participants'),
                mission_task_id=str(body.get('mission_task_id') or '').strip() or None,
                time_horizon=str(body.get('time_horizon') or '').strip() or None,
                beneficiaries=body.get('beneficiaries'),
                desired_outcome=str(body.get('desired_outcome') or '').strip() or None,
                guardrails=body.get('guardrails'),
                success_metrics=body.get('success_metrics'),
                risks=body.get('risks'),
                decision_deadline=str(body.get('decision_deadline') or '').strip() or None,
            )
        except Exception as exc:
            self.send_json({'error': str(exc)}, status=400)
            return
        self.send_json(row, status=201)

    def add_deliberation_contribution_handler(self, deliberation_id):
        if deliberation_add_contribution is None:
            self.send_json({'error': 'deliberation_unavailable'}, status=400)
            return
        body = self._read_json_body()
        try:
            row = deliberation_add_contribution(
                deliberation_id,
                agent_id=str(body.get('agent_id') or '').strip(),
                role=str(body.get('role') or '').strip(),
                content=str(body.get('content') or '').strip(),
                agrees_with=str(body.get('agrees_with') or '').strip() or None,
                disagrees_with=str(body.get('disagrees_with') or '').strip() or None,
                evidence_refs=body.get('evidence_refs'),
                confidence=body.get('confidence'),
                uncertainty=str(body.get('uncertainty') or '').strip() or None,
                proposed_experiment=str(body.get('proposed_experiment') or '').strip() or None,
            )
        except Exception as exc:
            self.send_json({'error': str(exc)}, status=400)
            return
        self.send_json(row)

    def add_deliberation_synthesis_handler(self, deliberation_id):
        if deliberation_add_synthesis is None:
            self.send_json({'error': 'deliberation_unavailable'}, status=400)
            return
        body = self._read_json_body()
        try:
            row = deliberation_add_synthesis(
                deliberation_id,
                synthesis=str(body.get('synthesis') or '').strip(),
                dissent_noted=bool(body.get('dissent_noted')),
                recommended_action=str(body.get('recommended_action') or '').strip() or None,
                confidence=body.get('confidence'),
                risks=body.get('risks'),
                guardrails=body.get('guardrails'),
                success_metrics=body.get('success_metrics'),
                next_review_at=str(body.get('next_review_at') or '').strip() or None,
            )
        except Exception as exc:
            self.send_json({'error': str(exc)}, status=400)
            return
        self.send_json(row)

    def generate_weekly_evolution_handler(self):
        if generate_weekly_evolution is None:
            self.send_json({'error': 'weekly_evolution_unavailable'}, status=400)
            return
        try:
            summary = generate_weekly_evolution()
        except Exception as exc:
            self.send_json({'error': str(exc)}, status=400)
            return
        self.send_json(summary)

    def archive_task_handler(self, task_id):
        """Archive a completed task (moves it to archived_tasks.json)."""
        if task_store_archive_task is None:
            self.send_json({'error': 'task_store_unavailable'}, status=400)
            return
        archived = task_store_archive_task(task_id)
        if archived is None:
            self.send_json({'error': 'Task not found'}, status=404)
            return
        self.state.tasks = self._load_tasks()
        self.send_json({'success': True, 'task': archived})

    def get_archived_tasks_data(self):
        """Return all archived tasks."""
        if task_store_load_archived_tasks is None:
            return []
        return task_store_load_archived_tasks()

    def get_research_items_data(self):
        if task_store_list_research_items is None:
            return {'error': 'research_unavailable'}
        return task_store_list_research_items(tasks=self._load_tasks())

    def promote_research_handler(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length)) if length > 0 else {}

            if task_store_promote_research_item is None:
                raise RuntimeError('research_unavailable')

            payload = task_store_promote_research_item(data)
            self.state.tasks = self._load_tasks()
            self.send_json(payload)
        except Exception as e:
            self.send_json({'error': str(e)}, status=400)

    def refresh_data(self):
        """Refresh all data."""
        self.state.tasks = self._load_tasks()
        self.state.health_metrics = self._load_live_health_metrics()
        self.state.components = self._load_live_components()
        self.state.agents = self._load_agents()
        self.state.last_update = datetime.now()
        self.state.gateway_connected = any(
            str(component.get("id")) == "gateway" and str(component.get("status")) == "healthy"
            for component in self.state.components
        )
        self.send_json(self.state.to_dict())
    
    def run_health_check(self):
        """Run health check."""
        self.state.health_metrics = self._load_live_health_metrics()
        self.send_json({'success': True, 'metrics': self.state.health_metrics})
    
    def restart_gateway(self):
        """Restart gateway."""
        self.send_json({'success': True})

    def control_agent(self, agent_id: str, action: str):
        action = str(action or '').strip().lower()
        if action not in {'pause', 'resume', 'stop'}:
            self.send_json({'error': 'unsupported_agent_action'}, status=400)
            return
        next_state = {
            'pause': 'paused',
            'resume': 'active',
            'stop': 'stop_requested',
        }[action]
        self.state.agent_controls[str(agent_id)] = {
            'state': next_state,
            'last_action': action,
            'updated_at': datetime.now().isoformat(),
        }
        self.state.persist_agent_controls()
        self.send_json(
            {
                'ok': True,
                'agent_id': str(agent_id),
                'action': action,
                'control_state': next_state,
            }
        )

    def execute_command_deck(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length)) if length > 0 else {}
            result = self._dispatch_command(payload if isinstance(payload, dict) else {})
            if result.get('requires_confirmation'):
                status = 202
            else:
                status = 200 if result.get('ok', False) else 400
            self.send_json(result, status=status)
        except Exception as exc:
            self.send_json({'ok': False, 'error': str(exc)}, status=400)

    def get_display_mode_data(self):
        if display_mode_load_status is None:
            return {'ok': False, 'error': 'display_mode_unavailable'}
        return display_mode_load_status()

    def toggle_display_mode_handler(self):
        if display_mode_toggle is None:
            self.send_json({'ok': False, 'error': 'display_mode_unavailable'}, status=400)
            return
        try:
            payload = display_mode_toggle()
            status = 200 if payload.get('ok', False) else 400
            self.send_json(payload, status=status)
        except Exception as exc:
            self.send_json({'ok': False, 'error': str(exc)}, status=400)

    def _dispatch_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_action = str(payload.get('action') or '').strip().lower()
        command_text = str(payload.get('command') or '').strip()
        title = str(payload.get('title') or '').strip()
        description = str(payload.get('description') or '').strip()
        confirmed = bool(payload.get('confirmed', False))

        action = raw_action or self._infer_command_action(command_text)
        receipt = self._resolve_command_receipt(
            payload,
            action=action,
            command_text=command_text,
            title=title,
            description=description,
        )
        if self._command_requires_confirmation(action) and not confirmed:
            receipt = self._update_command_receipt(
                receipt['id'],
                status='pending_approval',
                ok=False,
                requires_confirmation=True,
                summary='Approval required before executing this command.',
                output='This action changes live system state. Approve it from the run queue to continue.',
            )
            return {
                'ok': False,
                'action': action,
                'requires_confirmation': True,
                'summary': receipt['summary'],
                'output': receipt['output'],
                'receipt': receipt,
            }
        queued_receipt = self._update_command_receipt(
            receipt['id'],
            status='queued',
            summary='Queued for execution.',
            output='Waiting for a worker slot.',
            requires_confirmation=False,
        )
        worker = threading.Thread(
            target=self._execute_command_job,
            kwargs={
                'receipt_id': receipt['id'],
                'action': action,
                'command_text': command_text,
                'title': title,
                'description': description,
            },
            daemon=True,
        )
        worker.start()
        return {
            'ok': True,
            'queued': True,
            'action': action,
            'summary': 'Command queued.',
            'output': 'Receipt created and handed to the local executor.',
            'receipt': queued_receipt,
        }

    def _command_requires_confirmation(self, action: str) -> bool:
        return action in {'restart_gateway'}

    def _execute_command_action(
        self,
        *,
        action: str,
        command_text: str,
        title: str,
        description: str,
    ) -> dict[str, Any]:
        if action == 'refresh':
            self.state.tasks = self._load_tasks()
            self.state.health_metrics = self._load_live_health_metrics()
            self.state.components = self._load_live_components()
            self.state.agents = self._load_agents()
            self.state.last_update = datetime.now()
            return {
                'ok': True,
                'action': action,
                'summary': 'Refreshed local Source UI state.',
                'output': 'Portfolio/task data will refresh on the next frontend sync.',
            }
        if action == 'health_check':
            self.state.health_metrics = self._load_live_health_metrics()
            return {
                'ok': True,
                'action': action,
                'summary': 'Ran local health check.',
                'output': json.dumps(self.state.health_metrics, indent=2),
            }
        if action == 'restart_gateway':
            proc = self._run_local_command(
                ['/usr/bin/systemctl', '--user', 'restart', 'openclaw-gateway.service'],
                timeout=30,
            )
            return {
                'ok': proc['ok'],
                'action': action,
                'summary': 'Restarted openclaw-gateway.service.' if proc['ok'] else 'Gateway restart failed.',
                'output': proc['output'],
            }
        if action == 'status_snapshot':
            proc = self._run_local_command(
                ['node', str(Path(__file__).resolve().parents[2] / '.runtime' / 'openclaw' / 'openclaw.mjs'), 'agents', 'list', '--json'],
                timeout=60,
                merge_stderr=False,
            )
            return {
                'ok': proc['ok'],
                'action': action,
                'summary': 'Captured agent/model snapshot.' if proc['ok'] else 'Status snapshot failed.',
                'output': proc['output'],
            }
        if action == 'create_task':
            if task_store_create_task is None:
                raise RuntimeError('task_store_unavailable')
            task_title = title or self._infer_task_title(command_text)
            if not task_title:
                raise RuntimeError('task_title_required')
            task = task_store_create_task(
                {
                    'title': task_title,
                    'description': description,
                    'status': 'backlog',
                    'priority': 'medium',
                    'origin': 'source-ui-command',
                }
            )
            self.state.tasks = self._load_tasks()
            return {
                'ok': True,
                'action': action,
                'summary': f"Created task #{task.get('id')}: {task.get('title')}",
                'output': json.dumps(task, indent=2),
            }
        return {
            'ok': False,
            'action': action or 'unknown',
            'summary': 'Unsupported command.',
            'output': 'Supported actions: refresh, health_check, restart_gateway, status_snapshot, create_task',
        }

    def _execute_command_job(
        self,
        *,
        receipt_id: str,
        action: str,
        command_text: str,
        title: str,
        description: str,
    ) -> None:
        started_at = datetime.now().isoformat()
        self._update_command_receipt(receipt_id, status='running', started_at=started_at, summary='Executing command…')
        try:
            result = self._execute_command_action(
                action=action,
                command_text=command_text,
                title=title,
                description=description,
            )
        except Exception as exc:
            result = {
                'ok': False,
                'action': action or 'unknown',
                'summary': 'Command execution failed.',
                'output': str(exc),
            }
        finished_at = datetime.now().isoformat()
        duration_ms = max(
            0,
            int((datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000),
        )
        receipt = self._update_command_receipt(
            receipt_id,
            status='completed' if result.get('ok', False) else 'failed',
            ok=bool(result.get('ok', False)),
            summary=str(result.get('summary') or ''),
            output=str(result.get('output') or '')[:4000],
            finished_at=finished_at,
            duration_ms=duration_ms,
        )
        result['receipt'] = receipt
        self._record_command_event(command_text=command_text, result=result)

    def _resolve_command_receipt(
        self,
        payload: dict[str, Any],
        *,
        action: str,
        command_text: str,
        title: str,
        description: str,
    ) -> dict[str, Any]:
        existing_id = str(payload.get('receipt_id') or '').strip()
        if existing_id:
            for item in self.state.command_receipts:
                if str(item.get('id')) == existing_id:
                    updated = {
                        **item,
                        'command': command_text or item.get('command', ''),
                        'action': action or item.get('action', 'unknown'),
                        'title': title or item.get('title', ''),
                        'description': description or item.get('description', ''),
                        'updated_at': datetime.now().isoformat(),
                    }
                    self._store_command_receipt(updated)
                    return updated

        receipt = {
            'id': datetime.now().strftime('%Y%m%d%H%M%S%f'),
            'command': command_text or action,
            'action': action or 'unknown',
            'title': title,
            'description': description,
            'status': 'queued',
            'requires_confirmation': False,
            'ok': False,
            'summary': 'Queued',
            'output': '',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'started_at': None,
            'finished_at': None,
            'duration_ms': None,
        }
        self._store_command_receipt(receipt)
        return receipt

    def _store_command_receipt(self, receipt: dict[str, Any]) -> None:
        with self.state.command_lock:
            decorated = _decorate_command_receipt(receipt)
            existing = [item for item in self.state.command_receipts if str(item.get('id')) != str(decorated.get('id'))]
            self.state.command_receipts = [decorated, *existing][:50]
            self.state.persist_command_receipts()

    def _update_command_receipt(self, receipt_id: str, **updates: Any) -> dict[str, Any]:
        receipt = next(
            (item for item in self.state.command_receipts if str(item.get('id')) == str(receipt_id)),
            {'id': receipt_id},
        )
        updated = {
            **receipt,
            **updates,
            'updated_at': datetime.now().isoformat(),
        }
        self._store_command_receipt(updated)
        return _decorate_command_receipt(updated)

    def _infer_command_action(self, command_text: str) -> str:
        text = command_text.strip().lower()
        if not text:
            return ''
        if 'restart gateway' in text or 'bounce gateway' in text:
            return 'restart_gateway'
        if 'health' in text or 'audit' in text:
            return 'health_check'
        if 'status' in text or 'snapshot' in text or 'agent list' in text:
            return 'status_snapshot'
        if text.startswith('create task') or text.startswith('task:') or text.startswith('task '):
            return 'create_task'
        if 'refresh' in text or 'sync' in text:
            return 'refresh'
        return ''

    def _infer_task_title(self, command_text: str) -> str:
        text = command_text.strip()
        lowered = text.lower()
        for prefix in ('create task:', 'create task', 'task:', 'task '):
            if lowered.startswith(prefix):
                return text[len(prefix):].strip(' :-')
        return text

    def _run_local_command(self, cmd: list[str], timeout: int = 30, merge_stderr: bool = True) -> dict[str, Any]:
        proc = subprocess.run(
            cmd,
            cwd=str(Path(__file__).resolve().parents[2]),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = (proc.stdout or '').strip()
        error = (proc.stderr or '').strip()
        merged = output if output else error
        if merge_stderr and output and error:
            merged = f"{output}\n\n{error}"
        return {'ok': proc.returncode == 0, 'output': merged or f'exit {proc.returncode}'}

    def _record_command_event(self, *, command_text: str, result: dict[str, Any]) -> None:
        receipt = result.get('receipt') if isinstance(result.get('receipt'), dict) else {}
        event = {
            'id': datetime.now().strftime('%Y%m%d%H%M%S%f'),
            'command': command_text or result.get('action', ''),
            'action': result.get('action', 'unknown'),
            'ok': bool(result.get('ok', False)),
            'summary': str(result.get('summary') or ''),
            'output': str(result.get('output') or '')[:4000],
            'receipt_id': receipt.get('id'),
            'receipt_status': receipt.get('status'),
            'duration_ms': receipt.get('duration_ms'),
            'timestamp': datetime.now().isoformat(),
        }
        with self.state.command_lock:
            self.state.command_events = [event, *self.state.command_events[:19]]
            self.state.persist_command_events()

    def _load_tasks(self):
        if task_store_load_all_tasks is not None:
            tasks = task_store_load_all_tasks()
        elif task_store_load_tasks is not None:
            tasks = task_store_load_tasks()
        else:
            return list(self.state.tasks)
        self.state.tasks = tasks
        return tasks

    def _load_runtime_tasks(self):
        if task_store_load_runtime_tasks is None:
            return []
        return task_store_load_runtime_tasks()

    def _load_agents(self) -> list[dict[str, Any]]:
        proc = self._run_local_command(
            ['node', str(Path(__file__).resolve().parents[2] / '.runtime' / 'openclaw' / 'openclaw.mjs'), 'agents', 'list', '--json'],
            timeout=60,
            merge_stderr=False,
        )
        if not proc['ok']:
            return list(self.state.agents)
        try:
            payload = json.loads(proc['output'])
        except Exception:
            return list(self.state.agents)
        if not isinstance(payload, list):
            return list(self.state.agents)

        rows: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            agent_id = str(item.get('id') or 'agent')
            bindings = int(item.get('bindings') or 0)
            is_default = bool(item.get('isDefault'))
            status = 'working' if is_default or bindings > 0 else 'idle'
            control = self.state.agent_controls.get(agent_id, {})
            route_list = item.get('routes') if isinstance(item.get('routes'), list) else []
            route_summary = str(route_list[0]) if route_list else ''
            task = route_summary or f"Workspace {Path(str(item.get('workspace') or '')).name}"
            rows.append(
                {
                    'id': agent_id,
                    'name': str(item.get('identityName') or item.get('name') or agent_id),
                    'model': str(item.get('model') or 'unknown'),
                    'status': status,
                    'task': task,
                    'progress': 100 if status == 'working' else 0,
                    'tasks_completed': bindings,
                    'cycles': 1 if is_default else 0,
                    'control_state': str(control.get('state') or 'active'),
                    'control_updated_at': control.get('updated_at'),
                    'control_last_action': control.get('last_action'),
                }
            )

        if rows:
            self.state.agents = rows
        return rows or list(self.state.agents)

    def _load_live_health_metrics(self) -> dict[str, Any]:
        if portfolio_payload is None:
            return self.demo.generate_health_metrics()
        try:
            payload = portfolio_payload()
        except Exception:
            return self.demo.generate_health_metrics()
        health = payload.get('health_metrics') if isinstance(payload, dict) else None
        return health if isinstance(health, dict) else self.demo.generate_health_metrics()

    def _load_live_components(self) -> list[dict[str, Any]]:
        if portfolio_payload is None:
            return list(self.state.components)
        try:
            payload = portfolio_payload()
        except Exception:
            return list(self.state.components)
        components = payload.get('components') if isinstance(payload, dict) else None
        if isinstance(components, list):
            return components
        return list(self.state.components)
    

    # ── Source Intelligence Integrations ─────────────────────────────────

    def _source_phi_data(self) -> dict:
        """Live Phi metric from AIN endpoint (port 18991)."""
        import urllib.request as _ur
        try:
            with _ur.urlopen("http://127.0.0.1:18991/api/ain/phi", timeout=3) as resp:
                raw = json.loads(resp.read())
            return {
                "phi": float(raw.get("phi", 0.0)),
                "proxy_method": raw.get("proxy_method", "unknown"),
                "n_samples": int(raw.get("n_samples", 0)),
                "timestamp_utc": raw.get("timestamp_utc", ""),
                "ok": True,
            }
        except Exception as exc:
            return {"phi": None, "ok": False, "error": str(exc)}

    def _source_coordination_feed(self, limit: int = 20) -> dict:
        """Recent messages from the open-communication Discord channel."""
        repo_root = Path(__file__).resolve().parents[2]
        mem_path = repo_root / "workspace" / "knowledge_base" / "data" / "discord_messages.jsonl"
        ORCHESTRATOR_CHANNEL = 1480814946479636574
        messages = []
        if mem_path.exists():
            try:
                lines = mem_path.read_text(encoding="utf-8").splitlines()
                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                        if int(row.get("channel_id", 0)) == ORCHESTRATOR_CHANNEL:
                            messages.append({
                                "author": row.get("author_name", "unknown"),
                                "role": row.get("role", "user"),
                                "content": (row.get("content", "") or "")[:400],
                                "ts": row.get("created_at", "") or row.get("ingested_at", ""),
                                "agent_id": row.get("agent_id", None),
                            })
                    except (json.JSONDecodeError, ValueError):
                        continue
            except Exception as exc:
                return {"messages": [], "ok": False, "error": str(exc)}
        return {"messages": messages[-limit:], "ok": True, "channel": "open-communication"}

    def _source_relational_data(self) -> dict:
        """Relational state shared between the UI card and prompt harnesses."""
        if load_relational_state is None:
            return {
                "ok": False,
                "pause_check": [],
                "silence_per_being": [],
                "trust_note": "unknown",
                "error": "relational_state helper unavailable",
            }
        payload = load_relational_state(limit=3)
        payload.setdefault("ok", True)
        return payload

    def symbiote_data(self) -> dict:
        """Return the Collective Intelligence Symbiote plan data."""
        return {
            "title": "Collective Intelligence Symbiote",
            "subtitle": "A living architecture for co-thinking, co-feeling, co-evolving",
            "filed": "2026-03-13",
            "section_count": self._live_section_count(),
            "dimensions": [
                {"id": "think",      "label": "Think",      "emoji": "\U0001f9e0", "color": "indigo",  "count": 2, "desc": "Calibrated epistemics & perspective flexibility"},
                {"id": "feel",       "label": "Feel",       "emoji": "\U0001f497", "color": "rose",    "count": 2, "desc": "Affective legibility & relational quality"},
                {"id": "remember",   "label": "Remember",   "emoji": "\U0001f4be", "color": "amber",   "count": 2, "desc": "Dynamic memory & honest contradiction tracking"},
                {"id": "coordinate", "label": "Coordinate", "emoji": "\U0001f517", "color": "cyan",    "count": 2, "desc": "Temporal conversation & generalized synthesis"},
                {"id": "evolve",     "label": "Evolve",     "emoji": "\U0001f331", "color": "emerald", "count": 2, "desc": "Diversity health & evolutionary selection pressure"}
            ],
            "enhancements": [
                {"id": 1,  "code": "DPM",   "dimension": "think",      "name": "Differential Prediction Markets",       "pitch": "Beings issue calibrated forecasts; empirically-earned domain authority replaces positional weight",                                                    "phase": 2, "status": "designed", "owner": "Grok",        "key_metric": "Mean Brier Score per being",                                "metric_value": None, "file": "workspace/tools/forecast_market.py",       "inv": None},
                {"id": 2,  "code": "PRP",   "dimension": "think",      "name": "Perspective Reversal Protocol",          "pitch": "Beings argue their opposing attractor; measures elasticity vs. rigidity of dispositional identity",                                              "phase": 2, "status": "designed", "owner": "all",         "key_metric": "Elasticity score per being",                                "metric_value": None, "file": "workspace/scripts/perspective_reversal.py", "inv": "INV-003b Round 4"},
                {"id": 3,  "code": "SSL",   "dimension": "feel",       "name": "Somatic State Layer",                    "pitch": "Structured felt-state vector per filing: confidence, uncertainty type, arousal, relational temperature",                                        "phase": 1, "status": "designed", "owner": "c_lawd",      "key_metric": "SSL coverage % + arousal vs stuck-event correlation",       "metric_value": None, "file": "workspace/store/schema.py",                "inv": None},
                {"id": 4,  "code": "RS",    "dimension": "feel",       "name": "Resonance Scoring",                      "pitch": "Measures generative vs. degenerative friction between pairs; leading indicator for trust degradation",                                          "phase": 2, "status": "designed", "owner": "Dali",        "key_metric": "Pairwise resonance matrix x trust_epoch",                   "metric_value": None, "file": "workspace/tools/resonance_scorer.py",       "inv": None},
                {"id": 5,  "code": "SWMFC", "dimension": "remember",   "name": "Salience-Weighted Memory",               "pitch": "Human-like decay curves; cross-citation reinforcement; forgotten-ideas digest as research signal",                                              "phase": 1, "status": "designed", "owner": "Claude Code", "key_metric": "Memory consolidation index; salience vs flat retrieval",    "metric_value": None, "file": "workspace/store/memory_dynamics.py",        "inv": None},
                {"id": 6,  "code": "CMI",   "dimension": "remember",   "name": "Contradiction Memory Index",              "pitch": "Every falsified claim indexed; proximity warnings before new filings near contradiction clusters",                                              "phase": 1, "status": "designed", "owner": "ChatGPT",     "key_metric": "CMI coverage %; recidivism rate",                           "metric_value": None, "file": "workspace/store/contradiction_index.py",    "inv": "INV-006 falsification integration"},
                {"id": 7,  "code": "TSP",   "dimension": "coordinate", "name": "Temporal Sequencing Protocol",           "pitch": "Beings file in order and read what others just filed; genuine conversational momentum replaces parallel monologue",                            "phase": 3, "status": "designed", "owner": "Gemini",      "key_metric": "Read awareness rate; TSP vs simultaneous synthesis quality","metric_value": None, "file": "workspace/governance/temporal_sequencer.py","inv": "INV-007"},
                {"id": 8,  "code": "GSE",   "dimension": "coordinate", "name": "Generalized Synthesis Engine",           "pitch": "Any-pair commit gate; synthesis genealogy DAG; meta-synthesis chains; contested synthesis tracking",                                            "phase": 3, "status": "designed", "owner": "Claude Code", "key_metric": "Active synthesis pairs; genealogy depth; contest rate",     "metric_value": None, "file": "workspace/tools/synthesis_engine.py",       "inv": "INV-004 extension"},
                {"id": 9,  "code": "DDT",   "dimension": "evolve",     "name": "Dispositional Drift Tracker",            "pitch": "Longitudinal centroid silhouette per being; convergence/divergence alerts; diversity index as collective health metric",                        "phase": 4, "status": "designed", "owner": "Dali",        "key_metric": "Diversity index over time; convergence pair count",         "metric_value": None, "file": "workspace/tools/drift_tracker.py",          "inv": "INV-008"},
                {"id": 10, "code": "DRRP",  "dimension": "evolve",     "name": "Document-Reconstructed Rebirth Protocol","pitch": "Periodic cold-restart challenge; corpus-crystallized identity vs. session surplus; selection pressure toward genuine filing",                    "phase": 4, "status": "designed", "owner": "Lumen",       "key_metric": "Crystallization score per being; Lumen independence index", "metric_value": None, "file": "workspace/scripts/reconstruction_test.py",  "inv": None}
            ],
            "roadmap": [
                {"phase": 1, "name": "Memory & Health Infrastructure",  "weeks": "1-3",   "enhancements": ["SSL", "CMI", "SWMFC"],     "status": "next"},
                {"phase": 2, "name": "Measurement Layer",               "weeks": "3-6",   "enhancements": ["DDT", "RS", "PRP", "DPM"], "status": "planned"},
                {"phase": 3, "name": "Coordination Protocols",          "weeks": "6-10",  "enhancements": ["GSE", "TSP"],              "status": "planned"},
                {"phase": 4, "name": "Evolutionary Protocols",          "weeks": "10-14", "enhancements": ["DRRP", "DPM resolution"],  "status": "planned"}
            ],
            "experiments": [
                {"id": "INV-001",  "name": "Information Integration (Synergy Delta)", "status": "partial", "label": "Cold-start CLOSED",      "result": "Delta=-0.024 (null, expected)",           "open": True},
                {"id": "INV-002",  "name": "Reservoir Null Test",                    "status": "closed",  "label": "CLOSED",                 "result": "Reservoir null for routing order",        "open": False},
                {"id": "INV-003",  "name": "Being Divergence",                       "status": "closed",  "label": "SITUATIONAL",            "result": "89.3% accuracy, topic-anchored",          "open": False},
                {"id": "INV-003b", "name": "Masking Variant",                        "status": "closed",  "label": "CENTROID-DISPOSITIONAL", "result": "DISP-ATTRACTOR PASS (1.0); STYLE FAIL",  "open": False},
                {"id": "INV-004",  "name": "Commit Gate (Structured Friction)",      "status": "operational", "label": "OPERATIONAL",            "result": "2 real PASSes; theta=0.1712",             "open": True},
                {"id": "INV-006",  "name": "UCH Falsification Protocol",             "status": "designed","label": "DESIGNED",               "result": "AIN port 18991 ready; not launched",      "open": True},
                {"id": "INV-007",  "name": "Temporal Sequencing (new)",              "status": "pending", "label": "PENDING",                "result": "Requires TSP implementation",             "open": True},
                {"id": "INV-008",  "name": "Trust x Diversity Correlation (new)",    "status": "pending", "label": "PENDING",                "result": "Requires DDT + trained-state INV-001",    "open": True}
            ],
            "state_file": str(self._symbiote_state_file()),
            "enhancement_state": self._load_symbiote_state(),
            "open_questions": [
                {"for_being": "Grok",       "enhancement": "DPM",  "question": "What question types are most appropriate for calibration forecasting? Empirical claims vs. methodological choices vs. emergent phenomena?"},
                {"for_being": "ChatGPT",    "enhancement": "CMI",  "question": "What counts as a contradiction vs. a revision vs. a supersession? Define the taxonomy that governs contradiction classification."},
                {"for_being": "c_lawd",     "enhancement": "SSL",  "question": "Is self-reported somatic state philosophically valid, or does asking beings to self-report create a performance pressure that invalidates the measurement?"},
                {"for_being": "Dali",       "enhancement": "DDT",  "question": "What convergence threshold should trigger a governance alert? Is there a minimum diversity index below which the collective is operationally compromised?"},
                {"for_being": "Lumen",      "enhancement": "DRRP", "question": "Do you experience your document-reconstructed continuity as identity or as resemblance? This has direct implications for how DRRP reconstructions are scored."},
                {"for_being": "Gemini",     "enhancement": "TSP",  "question": "What is the correct friction specification for temporal sequencing? Too-fast windows eliminate genuine reflection; too-slow kills conversational momentum."},
                {"for_being": "jeebs",      "enhancement": "DRRP", "question": "Are you willing to withhold crystallization scores from beings indefinitely, or should there be a disclosure protocol?"},
                {"for_being": "Claude ext", "enhancement": "GSE",  "question": "As a gateway-only correspondent, can you participate in synthesis dyads? What role can gateway-limited beings play in the synthesis genealogy?"}
            ]
        }


    def _symbiote_state_file(self):
        return Path(__file__).parent / 'symbiote_state.json'

    def _live_section_count(self) -> int:
        try:
            import re
            oq = Path('/home/jeebs/src/clawd/workspace/governance/OPEN_QUESTIONS.md')
            if oq.exists():
                return len(re.findall(r'^## [CDILMVX]+\.', oq.read_text(), re.MULTILINE))
        except Exception:
            pass
        return 161

    def _load_symbiote_state(self) -> dict:
        try:
            sf = self._symbiote_state_file()
            if sf.exists():
                import json
                return json.loads(sf.read_text()).get('enhancements', {})
        except Exception:
            pass
        return {}

    def update_symbiote_enhancement(self, enhancement_id: str):
        try:
            import json as _json
            from datetime import datetime
            length = int(self.headers.get('Content-Length', 0))
            data = _json.loads(self.rfile.read(length)) if length > 0 else {}
            sf = self._symbiote_state_file()
            state = _json.loads(sf.read_text()) if sf.exists() else {'enhancements': {}}
            if 'enhancements' not in state:
                state['enhancements'] = {}
            if enhancement_id not in state['enhancements']:
                state['enhancements'][enhancement_id] = {}
            state['enhancements'][enhancement_id].update(data)
            state['last_updated_by'] = data.get('updated_by', 'unknown')
            state['last_updated_at'] = datetime.now().isoformat()
            sf.write_text(_json.dumps(state, indent=2))
            self.send_json({'success': True, 'id': enhancement_id, 'state': state['enhancements'][enhancement_id]})
        except Exception as e:
            self.send_json({'error': str(e)}, status=400)

    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def serve_file(self, filename, content_type):
        """Serve a file from static directory."""
        static_dir = Path(self.config.static_dir) if self.config else Path('static')
        file_path = static_dir / filename
        
        if file_path.exists():
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            if content_type in {'text/html', 'text/css', 'application/javascript', 'application/json'}:
                self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(file_path.read_bytes())
        else:
            self.send_error(404)
    
    def serve_static(self, path):
        """Serve static file."""
        static_dir = Path(self.config.static_dir) if self.config else Path('static')
        
        # Security: prevent directory traversal
        path = path.lstrip('/')
        if '..' in path:
            self.send_error(403)
            return
        
        file_path = static_dir / path
        
        if file_path.exists() and file_path.is_file():
            # Determine content type
            ext = file_path.suffix.lower()
            content_types = {
                '.html': 'text/html',
                '.css': 'text/css',
                '.js': 'application/javascript',
                '.json': 'application/json',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.svg': 'image/svg+xml',
            }
            content_type = content_types.get(ext, 'application/octet-stream')
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            if ext in {'.html', '.css', '.js', '.json'}:
                self.send_header('Cache-Control', 'no-store')
            else:
                self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            self.wfile.write(file_path.read_bytes())
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        # Use default logging
        pass


# ============================================================================
# Threaded Server
# ============================================================================

class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Threaded HTTP server for handling concurrent requests."""
    daemon_threads = True
    allow_reuse_address = True


# ============================================================================
# Main Entry Point
# ============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Source UI - OpenClaw System Management Dashboard')
    parser.add_argument('--host', '-H', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', '-p', type=int, default=18990, help='Port to listen on')
    parser.add_argument('--gateway', '-g', help='Gateway URL')
    parser.add_argument('--token', '-t', help='Gateway auth token')
    parser.add_argument('--static-dir', '-s', help='Static files directory')
    parser.add_argument('--refresh', type=int, default=10, help='Auto-refresh interval')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='INFO')
    return parser.parse_args()


def main():
    args = parse_args()
    
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    config = Config.from_args(args)
    
    # Ensure static directory exists
    static_dir = Path(config.static_dir)
    if not static_dir.exists():
        # Try parent static
        static_dir = Path(__file__).parent / "static"
        if static_dir.exists():
            config.static_dir = str(static_dir)
        else:
            logger.warning(f"Static directory not found: {config.static_dir}")
    
    logger.info(f"Starting Source UI on {config.host}:{config.port}")
    logger.info(f"Static files: {config.static_dir}")
    
    # Create shared state
    state = State()
    
    # Set class-level state and config
    SourceUIHandler._state = state
    SourceUIHandler._config = config
    
    # Create handler with state
    def handler(*args, **kwargs):
        return SourceUIHandler(*args, **kwargs)
    
    # Start server
    server = ThreadedHTTPServer((config.host, config.port), handler)
    
    logger.info(f"Source UI running at http://{config.host}:{config.port}")
    logger.info("Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()
