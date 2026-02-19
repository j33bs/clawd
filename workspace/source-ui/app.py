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
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import socketserver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('source-ui')


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
            'gateway_connected': self.gateway_connected,
            'last_update': self.last_update.isoformat() if self.last_update else None
        }


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
        # Initialize demo data
        if self._state and not self._state.agents:
            demo = DemoDataGenerator()
            self._state.agents = demo.generate_agents()
            self._state.tasks = demo.generate_tasks()
            self._state.scheduled_jobs = demo.generate_scheduled_jobs()
            self._state.components = demo.generate_components()
            self._state.logs = demo.generate_logs()
            self._state.health_metrics = demo.generate_health_metrics()
        
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
        elif parsed.path == '/api/refresh':
            self.refresh_data()
        elif parsed.path == '/api/health/check':
            self.run_health_check()
        elif parsed.path == '/api/gateway/restart':
            self.restart_gateway()
        else:
            self.send_error(404)
    
    def do_PATCH(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/tasks/'):
            task_id = parsed.path.split('/')[-1]
            self.update_task(task_id)
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
            data = self.state.to_dict()
        elif path == 'agents':
            data = self.state.agents
        elif path == 'tasks':
            data = self.state.tasks
        elif path == 'schedule':
            data = self.state.scheduled_jobs
        elif path == 'health':
            data = self.state.health_metrics
        elif path == 'logs':
            data = self.state.logs
        else:
            data = {'error': 'Not found'}
        
        self.send_json(data)
    
    def create_task(self):
        """Create a new task."""
        try:
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length)) if length > 0 else {}
            
            task = {
                'id': int(datetime.now().timestamp() * 1000),
                'created_at': datetime.now().isoformat(),
                **data
            }
            if 'status' not in task:
                task['status'] = 'backlog'
            
            self.state.tasks.append(task)
            self.send_json(task)
        except Exception as e:
            self.send_json({'error': str(e)}, status=400)
    
    def update_task(self, task_id):
        """Update a task."""
        try:
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length)) if length > 0 else {}
            
            for task in self.state.tasks:
                if str(task['id']) == task_id:
                    task.update(data)
                    self.send_json(task)
                    return
            
            self.send_json({'error': 'Task not found'}, status=404)
        except Exception as e:
            self.send_json({'error': str(e)}, status=400)
    
    def delete_task(self, task_id):
        """Delete a task."""
        self.state.tasks = [t for t in self.state.tasks if str(t['id']) != task_id]
        self.send_json({'success': True})
    
    def refresh_data(self):
        """Refresh all data."""
        self.state.health_metrics = self.demo.generate_health_metrics()
        self.state.last_update = datetime.now()
        self.state.gateway_connected = False  # Would check real gateway
        self.send_json(self.state.to_dict())
    
    def run_health_check(self):
        """Run health check."""
        self.state.health_metrics = self.demo.generate_health_metrics()
        self.send_json({'success': True, 'metrics': self.state.health_metrics})
    
    def restart_gateway(self):
        """Restart gateway."""
        self.send_json({'success': True})
    
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
