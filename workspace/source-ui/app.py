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
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import urllib.error
import urllib.request
import socketserver

WORKSPACE_IMPORT_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_IMPORT_ROOT))

try:
    from api.portfolio import portfolio_payload
except Exception:  # pragma: no cover
    portfolio_payload = None

try:
    from api.task_store import (
        create_task as create_task_store_task,
        delete_task as delete_task_store_task,
        load_all_tasks as load_task_store_tasks,
        update_task as update_task_store_task,
    )
except Exception:  # pragma: no cover
    create_task_store_task = None
    delete_task_store_task = None
    load_task_store_tasks = None
    update_task_store_task = None

try:
    from api.trails import trails_heatmap_payload
except Exception:  # pragma: no cover
    trails_heatmap_payload = None

try:
    from api.tacti_cr import (
        get_arousal_status,
        get_dream_status,
        get_immune_status,
        get_peer_graph_status,
        get_skills,
        get_status_data,
        get_stigmergy_status,
        get_trails_status,
        query_stigmergy,
        run_dream_consolidation,
        trigger_trail,
    )
except Exception:  # pragma: no cover
    get_arousal_status = None
    get_dream_status = None
    get_immune_status = None
    get_peer_graph_status = None
    get_skills = None
    get_status_data = None
    get_stigmergy_status = None
    get_trails_status = None
    query_stigmergy = None
    run_dream_consolidation = None
    trigger_trail = None

try:
    from api import oracle_corpus
except Exception:  # pragma: no cover
    oracle_corpus = None

try:
    import oracle_priority
except Exception:  # pragma: no cover
    oracle_priority = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('source-ui')

SOURCE_UI_ROOT = Path(__file__).resolve().parent
SOURCE_MISSION_PATH = SOURCE_UI_ROOT / 'config' / 'source_mission.json'
LEGACY_SOURCE_MISSION_PATH = SOURCE_UI_ROOT / 'source_mission.json'
SOURCE_STATE_DIR = SOURCE_UI_ROOT / 'state'
SOURCE_RUNTIME_STATE_PATH = SOURCE_STATE_DIR / 'source_runtime_state.json'
BACKLOG_INGEST_STATE_PATH = SOURCE_STATE_DIR / 'backlog_ingest.json'
COMMAND_HISTORY_PATH = SOURCE_STATE_DIR / 'command_history.json'
MISSION_EVENT_LIMIT = 200
SOURCE_MISSION_TOP_LEVEL_RUNTIME_KEYS = ('notifications', 'handoffs', 'logs', 'updated_at')
SOURCE_MISSION_TASK_RUNTIME_KEYS = (
    'status',
    'progress',
    'status_reason',
    'assignee',
    'started_at',
    'completed_at',
    'updated_at',
    'last_outcome_kind',
    'last_outcome_summary',
    'last_outcome_at',
    'last_outcome_runtime_agent',
    'last_outcome_event_id',
    'reviewer_notes',
    'reviewed_by',
)
SOURCE_MISSION_TASK_AUTOGEN_KEYS = (
    'origin',
    'mission_task_id',
    'sequence',
    'progress',
    'status_reason',
    'started_at',
    'completed_at',
    'updated_at',
    'last_outcome_kind',
    'last_outcome_summary',
    'last_outcome_at',
    'last_outcome_runtime_agent',
    'last_outcome_event_id',
)
OPENCLAW_CLI_PATH = SOURCE_UI_ROOT.parents[1] / '.runtime' / 'openclaw' / 'openclaw.mjs'
REPO_ROOT = SOURCE_UI_ROOT.parents[1]
WORKSPACE_ROOT = REPO_ROOT / 'workspace'
LOCAL_ASSISTANT_CHAT_COMPLETIONS_URL = os.environ.get(
    'SOURCE_UI_ORACLE_LOCAL_CHAT_URL',
    'http://127.0.0.1:8001/v1/chat/completions',
)
LOCAL_ASSISTANT_CHAT_MODEL = os.environ.get('SOURCE_UI_ORACLE_LOCAL_MODEL', 'local-assistant')
ORACLE_ANSWER_CONTEXT_LIMIT = 6
ORACLE_ANSWER_CONTEXT_MAX_CHARS = 3600


def resolve_source_mission_path() -> Path:
    candidates = [SOURCE_MISSION_PATH]
    if LEGACY_SOURCE_MISSION_PATH != SOURCE_MISSION_PATH:
        candidates.append(LEGACY_SOURCE_MISSION_PATH)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return SOURCE_MISSION_PATH


def source_state_version_ns() -> Optional[int]:
    mtimes: list[int] = []
    for path in (resolve_source_mission_path(), SOURCE_RUNTIME_STATE_PATH):
        if not path.exists():
            continue
        try:
            mtimes.append(path.stat().st_mtime_ns)
        except OSError:
            logger.exception("Failed to stat %s", path)
    if not mtimes:
        return None
    return max(mtimes)


def _task_counts_payload(tasks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        'backlog': sum(1 for task in tasks if DemoDataGenerator.normalize_task_status(task.get('status')) == 'backlog'),
        'in_progress': sum(1 for task in tasks if DemoDataGenerator.normalize_task_status(task.get('status')) == 'in_progress'),
        'review': sum(1 for task in tasks if DemoDataGenerator.normalize_task_status(task.get('status')) == 'review'),
        'done': sum(1 for task in tasks if DemoDataGenerator.normalize_task_status(task.get('status')) == 'done'),
    }


def _load_live_board_tasks() -> Optional[list[dict[str, Any]]]:
    if load_task_store_tasks is None:
        return None
    try:
        tasks = load_task_store_tasks()
    except Exception:
        logger.exception("Failed to load canonical task store payload")
        return None
    return [
        dict(task)
        for task in tasks
        if isinstance(task, dict) and str(task.get('origin') or '').strip() != 'source_mission_config'
    ]


def _run_command(args: list[str], timeout: float = 30.0) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return 1, '', str(exc)
    return completed.returncode, completed.stdout, completed.stderr


def _append_command_history_entry(
    *,
    action: str,
    command: str,
    ok: bool,
    summary: str,
    output: str,
    duration_ms: int = 0,
) -> dict[str, Any]:
    history = _read_json(COMMAND_HISTORY_PATH)
    rows = list(history) if isinstance(history, list) else []
    timestamp = datetime.now().isoformat()
    entry = {
        'id': datetime.now().strftime('%Y%m%d%H%M%S%f'),
        'command': command,
        'action': action,
        'ok': bool(ok),
        'summary': summary,
        'output': output,
        'duration_ms': int(duration_ms),
        'timestamp': timestamp,
    }
    rows.insert(0, entry)
    _write_json_atomic(COMMAND_HISTORY_PATH, rows[:100])
    return entry


def _runtime_portfolio() -> dict[str, Any]:
    if portfolio_payload is None:
        return {}
    try:
        payload = portfolio_payload()
    except Exception:
        logger.exception("Failed to build Source UI runtime portfolio")
        return {}
    return payload if isinstance(payload, dict) else {}


def _runtime_agents(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get('runtime_agents')
    return list(rows) if isinstance(rows, list) else []


def _runtime_scheduled_jobs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get('scheduled_jobs')
    return list(rows) if isinstance(rows, list) else []


def _runtime_logs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get('activity_logs')
    return list(rows) if isinstance(rows, list) else []


def _runtime_gateway_connected(payload: dict[str, Any]) -> bool:
    return bool(payload.get('gateway_connected'))


def _parse_isoish_timestamp(value: Any) -> Optional[datetime]:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


def _runtime_memory_system_status(payload: dict[str, Any]) -> dict[str, Any]:
    memory_ops = payload.get('memory_ops')
    if not isinstance(memory_ops, dict):
        return {}

    totals = memory_ops.get('totals') if isinstance(memory_ops.get('totals'), dict) else {}
    sources = [row for row in list(memory_ops.get('sources') or []) if isinstance(row, dict)]
    latest_source: Optional[dict[str, Any]] = None
    latest_updated_at: Optional[datetime] = None
    for row in sources:
        parsed = _parse_isoish_timestamp(row.get('updated_at'))
        if parsed is None:
            continue
        if latest_updated_at is None or parsed > latest_updated_at:
            latest_source = row
            latest_updated_at = parsed

    top_prompt_lines = [
        str(line).strip()
        for line in list(((memory_ops.get('preference_profile') or {}).get('top_prompt_lines') or []))
        if str(line).strip()
    ][:4]

    total_rows = int(totals.get('rows', 0) or 0)
    active_inferences = int(totals.get('inferences', 0) or 0)
    status = str(memory_ops.get('status') or '').strip().lower() or ('active' if total_rows else 'warning')
    if total_rows <= 0:
        status = 'warning'

    latest_text = latest_updated_at.isoformat() if latest_updated_at else None
    if not latest_text and latest_source is not None:
        latest_text = str(latest_source.get('updated_at') or '').strip() or None

    return {
        'status': status,
        'summary': str(memory_ops.get('summary') or f'{total_rows} total memory rows | {active_inferences} active inferences'),
        'total_rows': total_rows,
        'active_inferences': active_inferences,
        'source_count': len(sources),
        'latest_updated_at': latest_text,
        'latest_source_label': (str(latest_source.get('label') or '').strip() or None) if latest_source else None,
        'top_prompt_lines': top_prompt_lines,
    }


def _runtime_cron_status(payload: dict[str, Any], baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    jobs = [row for row in _runtime_scheduled_jobs(payload) if isinstance(row, dict)]
    if not jobs:
        return dict(baseline) if isinstance(baseline, dict) else {}

    enabled_jobs = [row for row in jobs if bool(row.get('enabled'))]
    live_jobs = enabled_jobs or jobs
    failing_jobs = [
        row
        for row in live_jobs
        if str(row.get('last_status') or '').strip().lower() not in {'', 'ok', 'success'}
    ]

    latest_run_dt: Optional[datetime] = None
    latest_run_text: Optional[str] = None
    next_run_dt: Optional[datetime] = None
    next_run_text: Optional[str] = None
    for row in live_jobs:
        last_run = str(row.get('last_run_at') or '').strip()
        parsed_last_run = _parse_isoish_timestamp(last_run)
        if parsed_last_run is not None and (latest_run_dt is None or parsed_last_run > latest_run_dt):
            latest_run_dt = parsed_last_run
            latest_run_text = last_run
        next_run = str(row.get('next_run_at') or '').strip()
        parsed_next_run = _parse_isoish_timestamp(next_run)
        if parsed_next_run is not None and (next_run_dt is None or parsed_next_run < next_run_dt):
            next_run_dt = parsed_next_run
            next_run_text = next_run

    status = 'ok'
    reason = 'live runtime schedule state'
    if not enabled_jobs:
        status = 'warning'
        reason = 'no enabled scheduled jobs'
    elif failing_jobs:
        status = 'warning'
        reason = f'{len(failing_jobs)} scheduled job(s) reported a non-ok status'

    detail = {
        'status': status,
        'reason': reason,
        'jobs_total': len(jobs),
        'enabled_jobs': len(enabled_jobs),
        'failing_jobs': len(failing_jobs),
        'template_jobs': len(jobs),
        'latest_artifact': 'openclaw cron runtime',
        'latest_artifact_ts': latest_run_text or next_run_text,
        'latest_run_at': latest_run_text,
        'next_run_at': next_run_text,
    }
    if isinstance(baseline, dict):
        for key in ('heartbeat_state_seen', 'template_error'):
            if key in baseline and key not in detail:
                detail[key] = baseline[key]
    return detail


def _fallback_oracle_query(
    question: str,
    *,
    k: int = 10,
    being: str | None = None,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    if oracle_corpus is None:
        raise RuntimeError('oracle corpus module unavailable')
    return oracle_corpus.build_lexical_oracle_payload(
        question,
        k=k,
        being=being,
        fallback_reason=fallback_reason,
    )


def _oracle_truthy(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if not normalized:
        return default
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    return default


def _oracle_answer_locations(payload: dict[str, Any], *, limit: int = 4) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for entry in list(payload.get('locations') or []):
        if not isinstance(entry, dict):
            continue
        location = str(entry.get('location') or '').strip()
        if not location or location in seen:
            continue
        rows.append(location)
        seen.add(location)
        if len(rows) >= limit:
            break
    if rows:
        return rows
    for row in list(payload.get('results') or []):
        if not isinstance(row, dict):
            continue
        location = str(row.get('location') or row.get('corpus_path') or '').strip()
        if not location or location in seen:
            continue
        rows.append(location)
        seen.add(location)
        if len(rows) >= limit:
            break
    return rows


def _oracle_answer_context(payload: dict[str, Any], *, limit: int = ORACLE_ANSWER_CONTEXT_LIMIT) -> str:
    blocks: list[str] = []
    total_chars = 0
    for index, row in enumerate(list(payload.get('results') or [])[: max(1, int(limit))], start=1):
        if not isinstance(row, dict):
            continue
        title = str(row.get('title') or row.get('source_label') or '').strip()
        source_label = str(row.get('source_label') or row.get('corpus_kind') or 'System Corpus').strip()
        location = str(row.get('location') or row.get('corpus_path') or '').strip()
        body = ' '.join(str(row.get('body') or '').split()).strip()
        if len(body) > 520:
            body = body[:519].rstrip() + '…'
        block = '\n'.join(
            bit
            for bit in (
                f'[{index}] {source_label}',
                f'title: {title}' if title else '',
                f'location: {location}' if location else '',
                f'excerpt: {body}' if body else '',
            )
            if bit
        )
        if not block:
            continue
        if total_chars + len(block) > ORACLE_ANSWER_CONTEXT_MAX_CHARS and blocks:
            break
        blocks.append(block)
        total_chars += len(block)
    return '\n\n'.join(blocks)


def _deterministic_oracle_answer(question: str, payload: dict[str, Any]) -> str:
    results = [row for row in list(payload.get('results') or []) if isinstance(row, dict)]
    sources = _oracle_answer_locations(payload)
    if not results:
        source_line = '; '.join(sources) if sources else 'none'
        return f'I could not find grounded local context for "{question}".\n\nSources: {source_line}'

    lead = ' '.join(str(results[0].get('body') or results[0].get('title') or '').split()).strip()
    if len(lead) > 260:
        lead = lead[:259].rstrip() + '…'
    if not lead:
        lead = f'The strongest local match is {str(results[0].get("title") or results[0].get("source_label") or "an unlabeled source").strip()}.'

    related_bits: list[str] = []
    for row in results[1:3]:
        title = str(row.get('title') or row.get('source_label') or '').strip()
        location = str(row.get('location') or row.get('corpus_path') or '').strip()
        if not title and not location:
            continue
        related_bits.append(f'{title} ({location})' if title and location else (title or location))

    answer = lead
    if related_bits:
        answer += '\n\nRelated context: ' + '; '.join(related_bits)
    answer += f'\n\nSources: {"; ".join(sources) if sources else "none"}'
    return answer


def _normalize_oracle_answer_text(text: str) -> str:
    lines: list[str] = []
    for raw_line in str(text or '').replace('**', '').splitlines():
        stripped = raw_line.strip()
        if stripped.startswith('*') and len(stripped) > 1 and stripped[1].isspace():
            stripped = stripped[1:].strip()
        elif stripped.startswith('-') and len(stripped) > 1 and stripped[1].isspace():
            stripped = stripped[1:].strip()
        lines.append(stripped if stripped else '')
    return '\n'.join(lines).strip()


def _query_local_oracle_answer(question: str, payload: dict[str, Any]) -> str:
    context = _oracle_answer_context(payload)
    if not context:
        return _deterministic_oracle_answer(question, payload)

    lease_owner = f"source-ui-oracle:{time.time_ns()}"
    lease = None
    if oracle_priority is not None:
        lease = oracle_priority.acquire_lease(
            lease_owner,
            purpose="source_ui_oracle",
            ttl_seconds=75.0,
            metadata={"question": str(question or "")[:160]},
            max_wait_seconds=12.0,
        )
        if lease is None:
            raise RuntimeError("oracle_priority_lease_unavailable")

    request_payload = {
        'model': LOCAL_ASSISTANT_CHAT_MODEL,
        'messages': [
            {
                'role': 'system',
                'content': (
                    'You answer questions about this local system using only the retrieved context. '
                    'Respond in plain text using short prose paragraphs instead of bullet lists, stay concise, and do not invent facts outside the context. '
                    'End with a final line starting with "Sources:" listing the most relevant locations.'
                ),
            },
            {
                'role': 'user',
                'content': (
                    f'Question: {question}\n\n'
                    f'Retrieved context:\n{context}\n\n'
                    'Write a direct answer grounded in the context above. '
                    'If the context is incomplete, say so plainly.'
                ),
            },
        ],
        'temperature': 0.15,
        'max_tokens': 320,
    }
    request = urllib.request.Request(
        LOCAL_ASSISTANT_CHAT_COMPLETIONS_URL,
        data=json.dumps(request_payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            raw = json.loads(response.read().decode('utf-8'))
    finally:
        if lease is not None and oracle_priority is not None:
            oracle_priority.release_lease(lease_owner)
    choices = list(raw.get('choices') or [])
    if not choices:
        raise RuntimeError('local oracle answer returned no choices')
    message = choices[0].get('message') if isinstance(choices[0], dict) else {}
    text = str(message.get('content') or '').strip()
    if not text:
        raise RuntimeError('local oracle answer returned empty content')
    return _normalize_oracle_answer_text(text)


def _augment_oracle_payload_with_answer(question: str, payload: dict[str, Any]) -> dict[str, Any]:
    answer_payload = dict(payload)
    try:
        answer_text = _query_local_oracle_answer(question, answer_payload)
    except Exception as exc:
        answer_payload['answer_error'] = str(exc)
        answer_text = _deterministic_oracle_answer(question, answer_payload)
        answer_payload['answer_mode'] = 'deterministic_fallback'
        answer_payload['answer_model'] = 'deterministic'
        answer_payload['answer_provider'] = 'source_ui'
    else:
        answer_payload['answer_mode'] = 'local_rag'
        answer_payload['answer_model'] = LOCAL_ASSISTANT_CHAT_MODEL
        answer_payload['answer_provider'] = 'local_vllm_assistant'
    if 'Sources:' not in answer_text:
        source_line = '; '.join(_oracle_answer_locations(answer_payload)) or 'none'
        answer_text = answer_text.rstrip() + f'\n\nSources: {source_line}'
    answer_payload['answer'] = answer_text
    return answer_payload


def _run_oracle_query(question: str, *, k: int = 10, being: str | None = None) -> dict[str, Any]:
    prompt = str(question or '').strip()
    if not prompt:
        raise ValueError('missing oracle query')

    try:
        top_k = int(k)
    except Exception:
        top_k = 10
    top_k = max(1, min(top_k, 20))
    being_filter = str(being or '').strip() or None

    system_payload = _fallback_oracle_query(prompt, k=top_k, being=being_filter)

    tools_dir = REPO_ROOT / 'workspace' / 'tools'
    store_dir = REPO_ROOT / 'workspace' / 'store'
    if str(store_dir) not in sys.path:
        sys.path.insert(0, str(store_dir))
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))

    import importlib.util
    try:
        oracle_path = tools_dir / 'oracle.py'
        spec = importlib.util.spec_from_file_location('source_ui_oracle', oracle_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f'failed to load oracle module from {oracle_path}')

        oracle_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle_mod)
        result = oracle_mod.query_corpus(prompt, k=top_k, being_filter=being_filter)
        if not isinstance(result, dict):
            raise RuntimeError('oracle query returned non-dict payload')

        trimmed_results: list[dict[str, Any]] = []
        for row in list(result.get('results') or [])[:top_k]:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            body = str(item.get('body') or '').strip()
            if len(body) > 320:
                body = body[:319].rstrip() + '…'
            item['source_label'] = 'Correspondence Semantic'
            item['corpus_kind'] = 'semantic_correspondence'
            item['corpus_path'] = str(oracle_corpus.ORACLE_CORRESPONDENCE_PATH if oracle_corpus is not None else WORKSPACE_ROOT / 'governance' / 'OPEN_QUESTIONS.md')
            item['location'] = str(oracle_corpus.ORACLE_CORRESPONDENCE_PATH if oracle_corpus is not None else WORKSPACE_ROOT / 'governance' / 'OPEN_QUESTIONS.md')
            item['relevance_score'] = item.get('relevance_score') or 1
            item['body'] = body
            trimmed_results.append(item)

        seen_keys = {
            (
                str(row.get('corpus_kind') or ''),
                str(row.get('section_number_filed') or ''),
                str(row.get('title') or ''),
                str(row.get('body') or ''),
            )
            for row in list(system_payload.get('results') or [])
            if isinstance(row, dict)
        }
        for row in trimmed_results:
            key = (
                str(row.get('corpus_kind') or ''),
                str(row.get('section_number_filed') or ''),
                str(row.get('title') or ''),
                str(row.get('body') or ''),
            )
            if key in seen_keys:
                continue
            if len(system_payload.get('results') or []) >= top_k:
                break
            system_payload.setdefault('results', []).append(row)
            seen_keys.add(key)

        payload = dict(system_payload)
        payload['question'] = prompt
        payload['k'] = top_k
        payload['source'] = 'system_corpus+semantic_correspondence'
        payload['semantic_model'] = str(result.get('model') or '')
        if being_filter:
            payload['being_filter'] = being_filter
        return payload
    except SystemExit as exc:
        system_payload['fallback_reason'] = str(exc)
    except Exception as exc:
        system_payload['fallback_reason'] = str(exc)

    return system_payload


def _merge_portfolio_status(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(data)
    components = payload.get('components')
    health_metrics = payload.get('health_metrics')
    if isinstance(components, list):
        merged['components'] = components
    if isinstance(health_metrics, dict):
        merged['health_metrics'] = health_metrics
    merged['agents'] = _runtime_agents(payload)
    merged['scheduled_jobs'] = _runtime_scheduled_jobs(payload)
    merged['logs'] = _runtime_logs(payload)
    merged['gateway_connected'] = _runtime_gateway_connected(payload)
    return merged


def _create_schedule_job(data: dict[str, Any]) -> dict[str, Any]:
    name = str(data.get('name') or '').strip()
    message = str(data.get('message') or '').strip()
    mode = str(data.get('mode') or 'cron').strip().lower()
    schedule_value = str(data.get('schedule') or '').strip()
    agent_id = str(data.get('agent_id') or data.get('agent') or 'main').strip() or 'main'
    timezone_name = str(data.get('tz') or '').strip()

    if not name:
        raise ValueError('schedule name required')
    if not message:
        raise ValueError('schedule message required')
    if not schedule_value:
        raise ValueError('schedule value required')
    if mode not in {'cron', 'every', 'at'}:
        raise ValueError('schedule mode must be cron, every, or at')
    if not OPENCLAW_CLI_PATH.exists():
        raise RuntimeError(f'OpenClaw CLI not found at {OPENCLAW_CLI_PATH}')

    args = ['node', str(OPENCLAW_CLI_PATH), 'cron', 'add', '--json', '--agent', agent_id, '--name', name, '--message', message]
    if mode == 'cron':
        args.extend(['--cron', schedule_value])
    elif mode == 'every':
        args.extend(['--every', schedule_value])
    else:
        args.extend(['--at', schedule_value])
    if timezone_name:
        args.extend(['--tz', timezone_name])
    if bool(data.get('announce')):
        args.append('--announce')
    if bool(data.get('disabled')):
        args.append('--disabled')

    started = time.perf_counter()
    code, stdout, stderr = _run_command(args, timeout=45.0)
    duration_ms = int((time.perf_counter() - started) * 1000)
    if code != 0:
        raise RuntimeError((stderr or stdout or f'cron add exited {code}').strip())
    try:
        payload = json.loads(stdout)
    except Exception as exc:
        raise RuntimeError(f'invalid cron add response: {exc}') from exc

    _append_command_history_entry(
        action='create_schedule',
        command=name,
        ok=True,
        summary=f'Created schedule {name}.',
        output='created',
        duration_ms=duration_ms,
    )
    return payload if isinstance(payload, dict) else {'success': True}


def _control_runtime_agent_action(agent_id: str, action: str) -> dict[str, Any]:
    normalized_agent_id = str(agent_id or '').strip()
    normalized_action = str(action or '').strip().lower()
    if normalized_action != 'stop':
        raise ValueError('unsupported agent action')

    started = time.perf_counter()
    if normalized_agent_id == 'service:dali-fishtank.service':
        code, stdout, stderr = _run_command(['systemctl', '--user', 'stop', 'dali-fishtank.service'], timeout=30.0)
        if code != 0:
            raise RuntimeError((stderr or stdout or 'failed to stop dali-fishtank.service').strip())
        duration_ms = int((time.perf_counter() - started) * 1000)
        _append_command_history_entry(
            action='stop_agent',
            command='dali-fishtank.service',
            ok=True,
            summary='Stopped Dali Fishtank.',
            output='stopped',
            duration_ms=duration_ms,
        )
        return {'success': True, 'summary': 'Stopped Dali Fishtank.'}

    if normalized_agent_id.startswith('work:'):
        work_id = normalized_agent_id.split(':', 1)[1]
        if work_id.startswith('local_exec'):
            code, stdout, stderr = _run_command(['bash', str(SOURCE_UI_ROOT.parents[1] / 'scripts' / 'local_exec_plane.sh'), 'stop'], timeout=30.0)
            if code != 0:
                raise RuntimeError((stderr or stdout or 'failed to stop local_exec worker').strip())
            duration_ms = int((time.perf_counter() - started) * 1000)
            _append_command_history_entry(
                action='stop_agent',
                command=work_id,
                ok=True,
                summary='Stopped local_exec worker.',
                output='stopped',
                duration_ms=duration_ms,
            )
            return {'success': True, 'summary': 'Stopped local_exec worker.'}

    raise ValueError('agent control unavailable for this runtime row')


def _extract_source_mission(payload: Any) -> Optional[dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    wrapped = payload.get('source_mission')
    if isinstance(wrapped, dict):
        return wrapped
    if any(
        key in payload
        for key in (
            'statement',
            'tagline',
            'north_star',
            'operating_commitments',
            'pillars',
            'tasks',
            'agents',
            'notifications',
            'handoffs',
            'logs',
        )
    ):
        return dict(payload)
    return None


def _wrap_source_mission_payload(source_mission: dict[str, Any], path: Path) -> dict[str, Any]:
    if path == LEGACY_SOURCE_MISSION_PATH:
        return {'source_mission': source_mission}
    return source_mission


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
        self.handoffs: list[dict] = []
        self.logs: list[dict] = []
        self.gateway_connected: bool = False
        self.last_update: Optional[datetime] = None
        self.source_mission_mtime_ns: Optional[int] = None
        
    def to_dict(self) -> dict:
        source_path = resolve_source_mission_path()
        source_exists = source_path.exists()
        source_updated_at = None
        task_counts = {
            'backlog': sum(1 for task in self.tasks if DemoDataGenerator.normalize_task_status(task.get('status')) == 'backlog'),
            'in_progress': sum(1 for task in self.tasks if DemoDataGenerator.normalize_task_status(task.get('status')) == 'in_progress'),
            'review': sum(1 for task in self.tasks if DemoDataGenerator.normalize_task_status(task.get('status')) == 'review'),
            'done': sum(1 for task in self.tasks if DemoDataGenerator.normalize_task_status(task.get('status')) == 'done'),
        }
        if source_exists:
            mission = DemoDataGenerator.load_source_mission()
            if isinstance(mission, dict):
                source_updated_at = mission.get('updated_at')
        return {
            'agents': self.agents,
            'tasks': self.tasks,
            'tasks_total': len(self.tasks),
            'task_counts': task_counts,
            'scheduled_jobs': self.scheduled_jobs,
            'health_metrics': self.health_metrics,
            'components': self.components,
            'notifications': self.notifications,
            'handoffs': self.handoffs,
            'logs': self.logs,
            'gateway_connected': self.gateway_connected,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'truth': {
                'source': 'source_mission' if source_exists else 'runtime_state',
                'source_mission_path': str(source_path),
                'source_mission_updated_at': source_updated_at,
            },
        }


def _read_json(path: Path) -> Any:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        logger.exception("Failed to parse %s", path)
        return None


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    tmp_path.replace(path)


def _read_source_runtime_state() -> dict[str, Any]:
    payload = _read_json(SOURCE_RUNTIME_STATE_PATH)
    return payload if isinstance(payload, dict) else {}


def _default_status_reason_for_task(task: dict[str, Any]) -> str:
    status = str(task.get('status') or 'backlog').strip()
    reasons = {
        'backlog': 'Queued in Source backlog.',
        'in_progress': 'Active lane work in progress.',
        'review': 'Awaiting review or follow-through.',
        'done': 'Completed and recorded.',
    }
    return reasons.get(status, 'Tracked in canonical mission state.')


def _extract_task_runtime_fields(task: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in SOURCE_MISSION_TASK_RUNTIME_KEYS:
        if key in task:
            payload[key] = task[key]
    return payload


def _sanitize_source_mission_task(task: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(task)
    for key in SOURCE_MISSION_TASK_AUTOGEN_KEYS:
        sanitized.pop(key, None)
    return sanitized


def _sanitize_source_mission_config(source_mission: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(source_mission)
    for key in SOURCE_MISSION_TOP_LEVEL_RUNTIME_KEYS:
        sanitized.pop(key, None)
    tasks = source_mission.get('tasks')
    if isinstance(tasks, list):
        sanitized['tasks'] = [
            _sanitize_source_mission_task(dict(task))
            for task in tasks
            if isinstance(task, dict)
        ]
    return sanitized


def _build_source_runtime_state(
    base_source_mission: dict[str, Any],
    current_source_mission: dict[str, Any],
) -> dict[str, Any]:
    base_tasks = [
        dict(task)
        for task in (base_source_mission.get('tasks') or [])
        if isinstance(task, dict)
    ]
    base_task_ids = {
        str(task.get('id') or '').strip()
        for task in base_tasks
        if str(task.get('id') or '').strip()
    }
    task_overrides: list[dict[str, Any]] = []
    extra_tasks: list[dict[str, Any]] = []
    for task in current_source_mission.get('tasks') or []:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get('id') or '').strip()
        if not task_id:
            continue
        if task_id in base_task_ids:
            runtime_fields = _extract_task_runtime_fields(task)
            if runtime_fields.get('status_reason') == _default_status_reason_for_task(task):
                runtime_fields.pop('status_reason', None)
            if runtime_fields:
                task_overrides.append({'id': task_id, **runtime_fields})
        else:
            extra_tasks.append(dict(task))

    runtime_state: dict[str, Any] = {
        'updated_at': str(current_source_mission.get('updated_at') or datetime.now().isoformat()),
    }
    if task_overrides:
        runtime_state['task_overrides'] = task_overrides
    if extra_tasks:
        runtime_state['extra_tasks'] = extra_tasks
    for key in ('notifications', 'handoffs', 'logs'):
        value = current_source_mission.get(key)
        if isinstance(value, list) and value:
            if key == 'logs':
                value = [
                    dict(item)
                    for item in value
                    if isinstance(item, dict) and (item.get('event_id') or item.get('metadata'))
                ]
                if not value:
                    continue
            runtime_state[key] = list(value)
    return runtime_state


def _merge_source_runtime_state(
    source_mission: dict[str, Any],
    runtime_state: dict[str, Any],
) -> dict[str, Any]:
    if not runtime_state:
        return source_mission

    merged = dict(source_mission)
    base_tasks = [
        dict(task)
        for task in (source_mission.get('tasks') or [])
        if isinstance(task, dict)
    ]
    overrides_by_id = {
        str(item.get('id') or '').strip(): dict(item)
        for item in (runtime_state.get('task_overrides') or [])
        if isinstance(item, dict) and str(item.get('id') or '').strip()
    }
    merged_tasks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for task in base_tasks:
        task_id = str(task.get('id') or '').strip()
        override = overrides_by_id.get(task_id)
        if override:
            task.update({key: value for key, value in override.items() if key != 'id'})
        merged_tasks.append(task)
        if task_id:
            seen_ids.add(task_id)

    for task in runtime_state.get('extra_tasks') or []:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get('id') or '').strip()
        if task_id and task_id in seen_ids:
            continue
        merged_tasks.append(dict(task))
        if task_id:
            seen_ids.add(task_id)

    merged['tasks'] = merged_tasks
    for key in ('notifications', 'handoffs', 'logs'):
        value = runtime_state.get(key)
        if isinstance(value, list):
            merged[key] = list(value)
    updated_at = str(runtime_state.get('updated_at') or '').strip()
    if updated_at:
        merged['updated_at'] = updated_at
    return merged


def _source_mission_contains_runtime_state(source_mission: dict[str, Any]) -> bool:
    if any(source_mission.get(key) for key in SOURCE_MISSION_TOP_LEVEL_RUNTIME_KEYS):
        return True
    for task in source_mission.get('tasks') or []:
        if not isinstance(task, dict):
            continue
        if any(key in task for key in SOURCE_MISSION_TASK_AUTOGEN_KEYS):
            return True
        if any(key in task for key in ('reviewer_notes', 'reviewed_by')):
            return True
    return False


def _normalize_source_mission_storage(
    source_path: Path,
    source_mission: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime_state = _read_source_runtime_state()
    if not _source_mission_contains_runtime_state(source_mission):
        return source_mission, runtime_state

    clean_source_mission = _sanitize_source_mission_config(source_mission)
    merged_source_mission = _merge_source_runtime_state(source_mission, runtime_state)
    normalized_runtime_state = _build_source_runtime_state(clean_source_mission, merged_source_mission)
    _write_json_atomic(SOURCE_RUNTIME_STATE_PATH, normalized_runtime_state)
    _write_json_atomic(source_path, _wrap_source_mission_payload(clean_source_mission, source_path))
    logger.info("Normalized Source UI mission storage into %s", SOURCE_RUNTIME_STATE_PATH)
    return clean_source_mission, normalized_runtime_state


def _next_numeric_id(items: list[dict], *, floor: int = 0) -> int:
    current = floor
    for item in items:
        try:
            current = max(current, int(item.get('id')))
        except Exception:
            continue
    return current + 1


def _append_notification(
    source_mission: dict[str, Any],
    *,
    event_id: str,
    kind: str,
    title: str,
    body: str,
    timestamp: str,
    metadata: Optional[dict[str, Any]] = None,
) -> bool:
    notifications = list(source_mission.get('notifications') or [])
    if any(str(item.get('event_id') or '') == event_id for item in notifications):
        return False
    entry = {
        'id': _next_numeric_id(notifications, floor=9000),
        'event_id': event_id,
        'type': kind,
        'title': title,
        'body': body,
        'timestamp': timestamp,
        'read': False,
    }
    if metadata:
        entry['metadata'] = metadata
    source_mission['notifications'] = [entry, *notifications][:MISSION_EVENT_LIMIT]
    return True


def _append_log(
    source_mission: dict[str, Any],
    *,
    event_id: str,
    level: str,
    message: str,
    timestamp: str,
    metadata: Optional[dict[str, Any]] = None,
) -> bool:
    logs = list(source_mission.get('logs') or [])
    if any(str(item.get('event_id') or '') == event_id for item in logs):
        return False
    entry = {
        'event_id': event_id,
        'level': level,
        'message': message,
        'timestamp': timestamp,
    }
    if metadata:
        entry['metadata'] = metadata
    source_mission['logs'] = [entry, *logs][:MISSION_EVENT_LIMIT]
    return True


def _append_handoff(source_mission: dict[str, Any], handoff: dict[str, Any]) -> bool:
    handoffs = list(source_mission.get('handoffs') or [])
    handoff_id = str(handoff.get('id') or '').strip()
    if handoff_id and any(str(item.get('id') or '') == handoff_id for item in handoffs):
        return False
    source_mission['handoffs'] = [handoff, *handoffs][:MISSION_EVENT_LIMIT]
    return True


def _backlog_event_id(task_id: str, kind: str, timestamp: str, seen_ts: Any) -> str:
    stamp = str(timestamp or '').strip()
    if not stamp:
        try:
            stamp = str(int(float(seen_ts or 0)))
        except Exception:
            stamp = '0'
    return f"backlog:{task_id}:{kind}:{stamp}"


def reconcile_backlog_state(
    source_mission: dict[str, Any],
    backlog_state: Any,
) -> tuple[dict[str, Any], bool]:
    if not isinstance(source_mission, dict) or not isinstance(backlog_state, dict):
        return source_mission, False

    tasks = [dict(task) for task in source_mission.get('tasks', []) if isinstance(task, dict)]
    task_by_id = {str(task.get('id') or '').strip(): task for task in tasks if str(task.get('id') or '').strip()}

    mission = dict(source_mission)
    mission['tasks'] = tasks
    mission['notifications'] = list(source_mission.get('notifications') or [])
    mission['logs'] = list(source_mission.get('logs') or [])
    mission['handoffs'] = list(source_mission.get('handoffs') or [])

    changed = False
    for assignee, entry in backlog_state.items():
        if assignee == '_history' or not isinstance(entry, dict):
            continue

        task_id = str(entry.get('task_id') or '').strip()
        kind = str(entry.get('outcome_kind') or '').strip().lower()
        if not task_id or kind not in {'result', 'blocker'}:
            continue

        task = task_by_id.get(task_id)
        if not isinstance(task, dict):
            continue

        timestamp = str(entry.get('outcome_at') or '').strip() or datetime.now().isoformat()
        event_id = _backlog_event_id(task_id, kind, timestamp, entry.get('outcome_seen_ts'))
        if str(task.get('last_outcome_event_id') or '').strip() == event_id:
            continue

        summary = str(entry.get('outcome_text') or '').strip()
        runtime_agent = str(entry.get('runtime_agent') or '').strip()
        before_status = str(task.get('status') or '').strip()

        if kind == 'result':
            task['status'] = 'review'
            task['progress'] = max(int(task.get('progress') or 0), 90)
            task['status_reason'] = summary or 'Runtime work returned for review.'
        else:
            task['status'] = 'backlog'
            task['status_reason'] = f"Blocked: {summary}" if summary else 'Blocked pending intervention.'

        task['updated_at'] = timestamp
        task['last_outcome_kind'] = kind
        task['last_outcome_summary'] = summary
        task['last_outcome_at'] = timestamp
        task['last_outcome_runtime_agent'] = runtime_agent
        task['last_outcome_event_id'] = event_id

        title = str(task.get('title') or task_id)
        kind_title = 'Work returned' if kind == 'result' else 'Blocker recorded'
        body = (
            f"{assignee} returned {title} for review."
            if kind == 'result'
            else f"{assignee} reported a blocker on {title}: {summary or 'see mission state'}"
        )
        log_message = (
            f"{title} moved {before_status or 'unknown'} -> {task['status']} via backlog outcome ({kind})."
        )
        handoff = {
            'id': event_id,
            'task_id': task_id,
            'mission_task_id': str(task.get('mission_task_id') or '').strip(),
            'task_title': title,
            'from_agent': assignee,
            'to_agent': 'source-ui',
            'kind': kind,
            'status': 'returned',
            'summary': summary or kind_title,
            'timestamp': timestamp,
            'runtime_agent': runtime_agent,
            'source': 'backlog_ingest',
        }
        metadata = {
            'task_id': task_id,
            'mission_task_id': handoff['mission_task_id'],
            'runtime_agent': runtime_agent,
            'source': 'backlog_ingest',
        }

        _append_notification(
            mission,
            event_id=event_id,
            kind='success' if kind == 'result' else 'warning',
            title=kind_title,
            body=body,
            timestamp=timestamp,
            metadata=metadata,
        )
        _append_log(
            mission,
            event_id=event_id,
            level='info' if kind == 'result' else 'warn',
            message=log_message,
            timestamp=timestamp,
            metadata=metadata,
        )
        _append_handoff(mission, handoff)
        changed = True

    return mission, changed


# ============================================================================
# Mission Task Normalization
# ============================================================================

class DemoDataGenerator:
    """Mission/task normalization helpers retained for Source UI state hydration."""

    PRIORITY_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    STATUS_ALIASES = {
        'todo': 'backlog',
        'queued': 'backlog',
        'queue': 'backlog',
        'pending': 'backlog',
        'open': 'backlog',
        'working': 'in_progress',
        'active': 'in_progress',
        'in-progress': 'in_progress',
        'in progress': 'in_progress',
        'reviewing': 'review',
        'qa': 'review',
        'complete': 'done',
        'completed': 'done',
        'closed': 'done',
    }
    PRIORITY_ALIASES = {
        'urgent': 'critical',
        'p0': 'critical',
        'p1': 'high',
        'normal': 'medium',
        'default': 'medium',
        'minor': 'low',
    }

    @staticmethod
    def default_definition_of_done(task: dict, artifact_path: str) -> str:
        description = str(task.get('description') or task.get('title') or 'Task').strip().rstrip('.')
        if artifact_path:
            return f"{description} and the canonical artifact at {artifact_path} is updated."
        return f"{description} is complete and reflected in canonical mission state."

    @staticmethod
    def default_status_reason(task: dict) -> str:
        return _default_status_reason_for_task(task)

    @classmethod
    def normalize_task_status(cls, status: Any) -> str:
        normalized = str(status or '').strip().lower().replace('-', '_').replace(' ', '_')
        if not normalized:
            return 'backlog'
        return cls.STATUS_ALIASES.get(normalized, normalized if normalized in {'backlog', 'in_progress', 'review', 'done'} else 'backlog')

    @classmethod
    def normalize_task_priority(cls, priority: Any) -> str:
        normalized = str(priority or '').strip().lower()
        if not normalized:
            return 'medium'
        return cls.PRIORITY_ALIASES.get(normalized, normalized if normalized in cls.PRIORITY_ORDER else 'medium')

    @classmethod
    def hydrate_task_metadata(cls, task: dict, *, index: int) -> tuple[dict, bool]:
        hydrated = dict(task)
        changed = False
        normalized_status = cls.normalize_task_status(hydrated.get('status'))
        if hydrated.get('status') != normalized_status:
            hydrated['status'] = normalized_status
            changed = True
        normalized_priority = cls.normalize_task_priority(hydrated.get('priority'))
        if hydrated.get('priority') != normalized_priority:
            hydrated['priority'] = normalized_priority
            changed = True
        artifact_path = str(hydrated.get('artifact_path') or '').strip()
        task_id = str(hydrated.get('id') or '').strip() or str(index + 1)
        mission_task_id = task_id if task_id.startswith('source-') else f"source-{task_id}"
        defaults = {
            'origin': 'source_mission_config',
            'mission_task_id': mission_task_id,
            'sequence': index + 1,
            'definition_of_done': cls.default_definition_of_done(hydrated, artifact_path),
            'status_reason': cls.default_status_reason(hydrated),
        }
        for key, value in defaults.items():
            if hydrated.get(key) in {None, ''}:
                hydrated[key] = value
                changed = True
        return hydrated, changed

    @staticmethod
    def normalize_tasks(tasks: list[dict]) -> tuple[list[dict], bool]:
        """Clamp progress and auto-complete tasks that reached 100%."""
        normalized: list[dict] = []
        changed = False

        for index, original_task in enumerate(tasks):
            task, task_changed = DemoDataGenerator.hydrate_task_metadata(dict(original_task), index=index)
            progress = task.get('progress')
            progress_value: Optional[int] = None

            if progress is not None:
                try:
                    progress_value = max(0, min(100, int(progress)))
                except (TypeError, ValueError):
                    progress_value = None
                else:
                    task['progress'] = progress_value

            if task.get('status') == 'done':
                if task.get('progress') != 100:
                    task['progress'] = 100
                task.setdefault('completed_at', datetime.now().isoformat())
            elif progress_value is not None and progress_value >= 100:
                task['status'] = 'done'
                task['progress'] = 100
                task.setdefault('completed_at', datetime.now().isoformat())

            if task_changed or task != original_task:
                changed = True
            normalized.append(task)

        return normalized, changed

    @classmethod
    def auto_start_backlog_tasks(cls, agents: list[dict], tasks: list[dict]) -> tuple[list[dict], bool]:
        """Move the next designated backlog task to in_progress for idle agents."""
        changed = False
        tasks_by_agent: dict[str, list[dict]] = {}

        for task in tasks:
            assignee = task.get('assignee')
            if assignee:
                tasks_by_agent.setdefault(str(assignee), []).append(task)

        def sort_key(task: dict) -> tuple:
            created_at = task.get('created_at') or task.get('createdAt') or ''
            return (
                cls.PRIORITY_ORDER.get(task.get('priority'), 99),
                str(created_at),
                str(task.get('sequence') or task.get('id') or ''),
            )

        for agent in agents:
            agent_id = str(agent.get('id', ''))
            if not agent_id:
                continue

            assigned_tasks = tasks_by_agent.get(agent_id, [])
            has_active_task = any(task.get('status') == 'in_progress' for task in assigned_tasks)
            if has_active_task:
                continue

            backlog_tasks = sorted(
                (
                    task
                    for task in assigned_tasks
                    if task.get('status') == 'backlog'
                    and str(task.get('origin') or '').strip() != 'source_mission_config'
                ),
                key=sort_key,
            )
            if not backlog_tasks:
                continue

            next_task = backlog_tasks[0]
            next_task['status'] = 'in_progress'
            next_task.setdefault('started_at', datetime.now().isoformat())
            next_task.setdefault('progress', 0)
            changed = True

        return tasks, changed

    @staticmethod
    def load_source_mission() -> Optional[dict[str, Any]]:
        source_path = resolve_source_mission_path()
        if not source_path.exists():
            return None
        source_mission = _extract_source_mission(_read_json(source_path))
        if not isinstance(source_mission, dict):
            return None
        source_mission, runtime_state = _normalize_source_mission_storage(source_path, source_mission)
        return _merge_source_runtime_state(source_mission, runtime_state)

    @staticmethod
    def sync_agents_with_tasks(agents: list[dict], tasks: list[dict]) -> list[dict]:
        synced_agents: list[dict] = []
        for agent in agents:
            agent_copy = dict(agent)
            assigned_tasks = [task for task in tasks if task.get('assignee') == agent_copy.get('id')]
            active_task = next((task for task in assigned_tasks if task.get('status') == 'in_progress'), None)
            completed_count = sum(1 for task in assigned_tasks if task.get('status') == 'done')
            base_completed = int(agent_copy.get('base_tasks_completed', agent_copy.get('tasks_completed', 0)))

            agent_copy['tasks_completed'] = base_completed + completed_count
            agent_copy['active_task_count'] = sum(
                1 for task in assigned_tasks if task.get('status') in {'backlog', 'in_progress', 'review'}
            )

            if active_task:
                agent_copy['status'] = 'working'
                agent_copy['task'] = active_task.get('title', 'Working mission task')
                agent_copy['progress'] = int(active_task.get('progress', 15))
            else:
                agent_copy['status'] = 'idle'
                agent_copy.pop('task', None)
                agent_copy.pop('progress', None)

            synced_agents.append(agent_copy)

        return synced_agents

    @classmethod
    def mission_seed(cls) -> Optional[dict[str, Any]]:
        source_mission = cls.load_source_mission()
        if not source_mission:
            return None

        source_mission, backlog_changed = reconcile_backlog_state(
            source_mission,
            _read_json(BACKLOG_INGEST_STATE_PATH),
        )
        mission_agents = source_mission.get('agents', [])
        if not isinstance(mission_agents, list):
            mission_agents = []
        tasks, tasks_normalized = cls.normalize_tasks(source_mission.get('tasks', []))
        tasks, tasks_auto_started = cls.auto_start_backlog_tasks(mission_agents, tasks)
        agents = cls.sync_agents_with_tasks(mission_agents, tasks)
        logs = source_mission.get('logs')
        if not isinstance(logs, list):
            logs = []
        notifications = source_mission.get('notifications', [])
        handoffs = source_mission.get('handoffs', [])

        return {
            'agents': agents,
            'tasks': tasks,
            'notifications': notifications,
            'handoffs': handoffs,
            'logs': logs,
            'tasks_reconciled': tasks_normalized or tasks_auto_started or backlog_changed,
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
        # Initialize state once on first request.
        if self._state and not self._state.agents and not self._state.tasks:
            mission_seed = DemoDataGenerator.mission_seed()
            if mission_seed:
                self._state.agents = mission_seed['agents']
                self._state.tasks = mission_seed['tasks']
                self._state.notifications = mission_seed['notifications']
                self._state.handoffs = mission_seed['handoffs']
                self._state.logs = mission_seed['logs']
            self._state.scheduled_jobs = []
            self._state.components = []
            self._state.health_metrics = {}
            self._state.last_update = datetime.now()
            if mission_seed:
                self.persist_source_mission()

        super().__init__(*args, **kwargs)
    
    @property
    def state(self):
        return self._state
    
    @property
    def config(self):
        return self._config

    def refresh_state_from_source_mission(self, force: bool = False) -> bool:
        """Reload state if the canonical mission file changed on disk."""
        if not resolve_source_mission_path().exists():
            return False

        mission_mtime_ns = source_state_version_ns()
        if mission_mtime_ns is None:
            return False

        if not force and self.state.source_mission_mtime_ns == mission_mtime_ns:
            return False

        mission_seed = DemoDataGenerator.mission_seed()
        if not mission_seed:
            return False

        self.state.agents = mission_seed['agents']
        self.state.tasks = mission_seed['tasks']
        self.state.notifications = mission_seed['notifications']
        self.state.handoffs = mission_seed['handoffs']
        self.state.logs = mission_seed['logs']
        self.state.last_update = datetime.now()
        self.state.source_mission_mtime_ns = mission_mtime_ns
        if mission_seed.get('tasks_reconciled'):
            self.persist_source_mission()
        return True
    
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
        elif parsed.path == '/api/schedule':
            self.create_schedule()
        elif parsed.path == '/api/tacti/dream/run':
            self.run_dream_consolidation_handler()
        elif parsed.path == '/api/hivemind/stigmergy/query':
            self.query_stigmergy_handler()
        elif parsed.path == '/api/hivemind/trails/trigger':
            self.trigger_trail_handler()
        elif parsed.path == '/api/oracle':
            self.query_oracle_handler()
        elif parsed.path == '/api/refresh':
            self.refresh_data()
        elif parsed.path == '/api/health/check':
            self.run_health_check()
        elif parsed.path == '/api/gateway/restart':
            self.restart_gateway()
        elif parsed.path.startswith('/api/agents/'):
            parts = [part for part in parsed.path.split('/') if part]
            if len(parts) == 4:
                _, _, agent_id, action = parts
                self.control_agent(agent_id, action)
            else:
                self.send_error(404)
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
        self.refresh_state_from_source_mission()
        board_tasks = _load_live_board_tasks()
        runtime_payload: dict[str, Any] = {}
        
        if path == 'status':
            data = self.state.to_dict()
            if board_tasks is not None:
                data['tasks'] = board_tasks
                data['tasks_total'] = len(board_tasks)
                data['task_counts'] = _task_counts_payload(board_tasks)
            runtime_payload = _runtime_portfolio()
            if runtime_payload:
                data = _merge_portfolio_status(data, runtime_payload)
                memory_system = _runtime_memory_system_status(runtime_payload)
                if memory_system:
                    data['memory_system'] = memory_system
                if isinstance(data.get('components'), list):
                    self.state.components = data['components']
                if isinstance(data.get('health_metrics'), dict):
                    self.state.health_metrics = data['health_metrics']
                self.state.gateway_connected = bool(data.get('gateway_connected'))
            if get_status_data is not None:
                try:
                    data.update(get_status_data())
                except Exception:
                    logger.exception("Failed to build TACTI status payload")
            if runtime_payload:
                cron_status = _runtime_cron_status(runtime_payload, data.get('cron') if isinstance(data.get('cron'), dict) else None)
                if cron_status:
                    data['cron'] = cron_status
            data.pop('knowledge_base_sync', None)
            data.setdefault('memory_system', {})
        elif path == 'portfolio':
            runtime_payload = _runtime_portfolio()
            if not runtime_payload:
                data = {'source_mission': self.current_source_mission()}
            else:
                data = runtime_payload
        elif path == 'world-better':
            runtime_payload = _runtime_portfolio()
            if not runtime_payload:
                data = {}
            else:
                data = runtime_payload.get('world_better', {})
        elif path == 'agents':
            runtime_payload = _runtime_portfolio()
            data = _runtime_agents(runtime_payload) if runtime_payload else self.state.agents
        elif path == 'tasks':
            data = board_tasks if board_tasks is not None else self.state.tasks
        elif path == 'handoffs':
            data = self.state.handoffs
        elif path == 'schedule':
            runtime_payload = _runtime_portfolio()
            data = _runtime_scheduled_jobs(runtime_payload) if runtime_payload else self.state.scheduled_jobs
        elif path == 'health':
            runtime_payload = _runtime_portfolio()
            data = runtime_payload.get('health_metrics', self.state.health_metrics) if runtime_payload else self.state.health_metrics
        elif path == 'logs':
            runtime_payload = _runtime_portfolio()
            data = _runtime_logs(runtime_payload) if runtime_payload else self.state.logs
        elif path == 'tacti/dream':
            if get_dream_status is None:
                self.send_json({'error': 'tacti_dream_unavailable'}, status=503)
                return
            try:
                data = get_dream_status(limit=20)
            except Exception as exc:
                self.send_json({'error': str(exc)}, status=500)
                return
        elif path == 'hivemind/stigmergy':
            if get_stigmergy_status is None:
                self.send_json({'error': 'stigmergy_unavailable'}, status=503)
                return
            try:
                data = get_stigmergy_status(limit=20)
            except Exception as exc:
                self.send_json({'error': str(exc)}, status=500)
                return
        elif path == 'tacti/immune':
            if get_immune_status is None:
                self.send_json({'error': 'semantic_immune_unavailable'}, status=503)
                return
            try:
                data = get_immune_status(limit=20)
            except Exception as exc:
                self.send_json({'error': str(exc)}, status=500)
                return
        elif path == 'tacti/arousal':
            if get_arousal_status is None:
                self.send_json({'error': 'arousal_unavailable'}, status=503)
                return
            try:
                data = get_arousal_status()
            except Exception as exc:
                self.send_json({'error': str(exc)}, status=500)
                return
        elif path == 'hivemind/trails':
            if get_trails_status is None:
                self.send_json({'error': 'trails_unavailable'}, status=503)
                return
            try:
                data = get_trails_status(limit=20)
            except Exception as exc:
                self.send_json({'error': str(exc)}, status=500)
                return
        elif path == 'hivemind/peer-graph':
            if get_peer_graph_status is None:
                self.send_json({'error': 'peer_graph_unavailable'}, status=503)
                return
            try:
                data = get_peer_graph_status(limit=20)
            except Exception as exc:
                self.send_json({'error': str(exc)}, status=500)
                return
        elif path == 'skills':
            if get_skills is None:
                self.send_json({'error': 'skills_unavailable'}, status=503)
                return
            try:
                data = get_skills(limit=100)
            except Exception as exc:
                self.send_json({'error': str(exc)}, status=500)
                return
        elif path == 'ain/status':
            data = self._ain_status_payload()
        elif path == 'ain/phi':
            data = self._ain_phi_payload()
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
        elif path == 'oracle':
            params = parse_qs(parsed.query)
            query = str((params.get('q') or params.get('query') or [''])[0] or '').strip()
            if not query:
                self.send_json({'error': 'missing oracle query'}, status=400)
                return
            try:
                k = int((params.get('k') or ['10'])[0] or 10)
            except Exception:
                k = 10
            being = str((params.get('being') or [''])[0] or '').strip() or None
            include_answer = _oracle_truthy((params.get('answer') or [''])[0] or None, default=False)
            try:
                data = _run_oracle_query(query, k=k, being=being)
                if include_answer:
                    data = _augment_oracle_payload_with_answer(query, data)
            except Exception as exc:
                logger.exception("Oracle query failed")
                self.send_json({'error': str(exc), 'question': query}, status=500)
                return
        else:
            self.send_json({'error': 'Not found'}, status=404)
            return
        
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

    def _ain_phi_payload(self) -> dict[str, Any]:
        try:
            with urllib.request.urlopen('http://127.0.0.1:18991/api/ain/phi', timeout=2.0) as resp:
                payload = json.loads(resp.read().decode('utf-8'))
            return payload if isinstance(payload, dict) else {'ok': False, 'error': 'invalid_ain_payload'}
        except Exception as exc:
            return {'ok': False, 'error': str(exc), 'phi': 0.0}

    def _ain_status_payload(self) -> dict[str, Any]:
        phi_payload = self._ain_phi_payload()
        running = bool(phi_payload.get('ok', True)) and 'error' not in phi_payload
        phi_value = float(phi_payload.get('phi') or 0.0)
        return {
            'running': running,
            'state': 'online' if running else 'offline',
            'total_drive': phi_value,
            'message': (
                f"AIN phi proxy active on 18991 (phi={phi_value:.4f})"
                if running
                else str(phi_payload.get('error') or 'AIN phi proxy unavailable')
            ),
        }

    def run_dream_consolidation_handler(self):
        if run_dream_consolidation is None:
            self.send_json({'error': 'tacti_dream_unavailable'}, status=503)
            return
        body = self._read_json_body()
        try:
            payload = run_dream_consolidation(day=str(body.get('day') or '').strip() or None)
        except Exception as exc:
            self.send_json({'error': str(exc)}, status=500)
            return
        self.send_json(payload)

    def query_stigmergy_handler(self):
        if query_stigmergy is None:
            self.send_json({'error': 'stigmergy_unavailable'}, status=503)
            return
        body = self._read_json_body()
        try:
            payload = query_stigmergy(str(body.get('query') or body.get('text') or ''), limit=20)
        except Exception as exc:
            self.send_json({'error': str(exc)}, status=500)
            return
        self.send_json(payload)

    def trigger_trail_handler(self):
        if trigger_trail is None:
            self.send_json({'error': 'trails_unavailable'}, status=503)
            return
        body = self._read_json_body()
        try:
            payload = trigger_trail(
                text=body.get('text'),
                tags=body.get('tags') if isinstance(body.get('tags'), list) else None,
                strength=body.get('strength'),
            )
        except Exception as exc:
            self.send_json({'error': str(exc)}, status=500)
            return
        self.send_json(payload)

    def query_oracle_handler(self):
        body = self._read_json_body()
        query = str(body.get('q') or body.get('query') or '').strip()
        if not query:
            self.send_json({'error': 'missing oracle query'}, status=400)
            return
        include_answer = _oracle_truthy(body.get('answer'), default=True)
        try:
            payload = _run_oracle_query(
                query,
                k=int(body.get('k') or 10),
                being=str(body.get('being') or '').strip() or None,
            )
            if include_answer:
                payload = _augment_oracle_payload_with_answer(query, payload)
        except Exception as exc:
            logger.exception("Oracle query failed")
            self.send_json({'error': str(exc), 'question': query}, status=500)
            return
        self.send_json(payload)
    
    def create_task(self):
        """Create a new task."""
        try:
            data = self._read_json_body()
            if create_task_store_task is not None:
                created_task = create_task_store_task(data)
                self.send_json(created_task)
                return

            sequence = max((int(task.get('sequence') or 0) for task in self.state.tasks), default=0) + 1
            task = {
                'id': int(datetime.now().timestamp() * 1000),
                'created_at': datetime.now().isoformat(),
                'sequence': sequence,
                'origin': 'source_ui_api',
                **data
            }
            if 'status' not in task:
                task['status'] = 'backlog'
            task, _ = DemoDataGenerator.hydrate_task_metadata(task, index=len(self.state.tasks))

            self.state.tasks.append(task)
            self.state.tasks, _ = DemoDataGenerator.normalize_tasks(self.state.tasks)
            self.state.tasks, _ = DemoDataGenerator.auto_start_backlog_tasks(self.state.agents, self.state.tasks)
            self.state.agents = DemoDataGenerator.sync_agents_with_tasks(self.state.agents, self.state.tasks)
            self.record_task_mutation('created', task)
            self.persist_source_mission()
            created_task = next((item for item in self.state.tasks if item.get('id') == task['id']), task)
            self.send_json(created_task)
        except Exception as e:
            self.send_json({'error': str(e)}, status=400)
    
    def update_task(self, task_id):
        """Update a task."""
        try:
            data = self._read_json_body()
            if update_task_store_task is not None:
                updated_task = update_task_store_task(task_id, data)
                if updated_task is None:
                    self.send_json({'error': 'Task not found'}, status=404)
                    return
                self.send_json(updated_task)
                return

            for task in self.state.tasks:
                if str(task['id']) == task_id:
                    previous_task = dict(task)
                    task.update(data)
                    self.state.tasks, _ = DemoDataGenerator.normalize_tasks(self.state.tasks)
                    self.state.tasks, _ = DemoDataGenerator.auto_start_backlog_tasks(self.state.agents, self.state.tasks)
                    self.state.agents = DemoDataGenerator.sync_agents_with_tasks(self.state.agents, self.state.tasks)
                    updated_task = next((item for item in self.state.tasks if str(item.get('id')) == task_id), task)
                    self.record_task_mutation('updated', updated_task, previous_task=previous_task)
                    self.persist_source_mission()
                    self.send_json(updated_task)
                    return
            
            self.send_json({'error': 'Task not found'}, status=404)
        except Exception as e:
            self.send_json({'error': str(e)}, status=400)
    
    def delete_task(self, task_id):
        """Delete a task."""
        if delete_task_store_task is not None:
            deleted = delete_task_store_task(task_id)
            if not deleted:
                self.send_json({'error': 'Task not found'}, status=404)
                return
            self.send_json({'success': True})
            return
        deleted_task = next((dict(task) for task in self.state.tasks if str(task['id']) == task_id), None)
        self.state.tasks = [t for t in self.state.tasks if str(t['id']) != task_id]
        self.state.agents = DemoDataGenerator.sync_agents_with_tasks(self.state.agents, self.state.tasks)
        if deleted_task:
            self.record_task_mutation('deleted', deleted_task)
        self.persist_source_mission()
        self.send_json({'success': True})
    
    def refresh_data(self):
        """Refresh all data."""
        board_tasks = _load_live_board_tasks()
        data = self.state.to_dict()
        if board_tasks is not None:
            data['tasks'] = board_tasks
            data['tasks_total'] = len(board_tasks)
            data['task_counts'] = _task_counts_payload(board_tasks)
        runtime_payload = _runtime_portfolio()
        if runtime_payload:
            data = _merge_portfolio_status(data, runtime_payload)
            if isinstance(data.get('components'), list):
                self.state.components = data['components']
            if isinstance(data.get('health_metrics'), dict):
                self.state.health_metrics = data['health_metrics']
            self.state.gateway_connected = bool(data.get('gateway_connected'))
        self.state.last_update = datetime.now()
        self.send_json(data)

    def run_health_check(self):
        """Run health check."""
        started = time.perf_counter()
        runtime_payload = _runtime_portfolio()
        metrics = runtime_payload.get('health_metrics') if isinstance(runtime_payload, dict) else None
        components = runtime_payload.get('components') if isinstance(runtime_payload, dict) else None
        if not isinstance(metrics, dict) or not isinstance(components, list):
            duration_ms = int((time.perf_counter() - started) * 1000)
            _append_command_history_entry(
                action='run_health_check',
                command='runtime_health',
                ok=False,
                summary='Failed to collect live runtime health snapshot.',
                output='runtime payload unavailable',
                duration_ms=duration_ms,
            )
            self.send_json({'error': 'runtime health unavailable'}, status=503)
            return
        if isinstance(metrics, dict):
            self.state.health_metrics = metrics
        if isinstance(components, list):
            self.state.components = components
        self.state.gateway_connected = _runtime_gateway_connected(runtime_payload)
        self.state.last_update = datetime.now()
        duration_ms = int((time.perf_counter() - started) * 1000)
        _append_command_history_entry(
            action='run_health_check',
            command='runtime_health',
            ok=bool(metrics),
            summary='Refreshed live runtime health snapshot.',
            output=f"metrics={len(metrics or {})} components={len(components or [])}",
            duration_ms=duration_ms,
        )
        self.send_json({
            'success': True,
            'metrics': self.state.health_metrics,
            'components': self.state.components,
            'gateway_connected': self.state.gateway_connected,
        })

    def restart_gateway(self):
        """Restart gateway."""
        started = time.perf_counter()
        code, stdout, stderr = _run_command(['systemctl', '--user', 'restart', 'openclaw-gateway.service'], timeout=45.0)
        duration_ms = int((time.perf_counter() - started) * 1000)
        if code != 0:
            detail = (stderr or stdout or 'failed to restart openclaw-gateway.service').strip()
            _append_command_history_entry(
                action='restart_gateway',
                command='openclaw-gateway.service',
                ok=False,
                summary='Gateway restart failed.',
                output=detail,
                duration_ms=duration_ms,
            )
            self.send_json({'error': detail}, status=500)
            return
        time.sleep(1.0)
        runtime_payload = _runtime_portfolio()
        self.state.gateway_connected = _runtime_gateway_connected(runtime_payload)
        self.state.last_update = datetime.now()
        _append_command_history_entry(
            action='restart_gateway',
            command='openclaw-gateway.service',
            ok=True,
            summary='Restarted gateway service.',
            output='restarted',
            duration_ms=duration_ms,
        )
        self.send_json({
            'success': True,
            'summary': 'Restarted gateway service.',
            'gateway_connected': self.state.gateway_connected,
        })

    def create_schedule(self):
        """Create a live scheduled job."""
        try:
            payload = _create_schedule_job(self._read_json_body())
        except ValueError as exc:
            self.send_json({'error': str(exc)}, status=400)
            return
        except Exception as exc:
            logger.exception("Failed to create Source UI schedule")
            self.send_json({'error': str(exc)}, status=500)
            return
        self.state.last_update = datetime.now()
        self.send_json(payload)

    def control_agent(self, agent_id: str, action: str):
        """Control a runtime-backed agent row."""
        try:
            payload = _control_runtime_agent_action(agent_id, action)
        except ValueError as exc:
            self.send_json({'error': str(exc)}, status=400)
            return
        except Exception as exc:
            logger.exception("Failed to control runtime agent row %s", agent_id)
            self.send_json({'error': str(exc)}, status=500)
            return
        self.state.last_update = datetime.now()
        self.send_json(payload)

    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def current_source_mission(self):
        source_mission = DemoDataGenerator.load_source_mission()
        if not source_mission:
            return None

        source_mission = dict(source_mission)
        source_mission['agents'] = self.state.agents
        source_mission['tasks'] = self.state.tasks
        source_mission['notifications'] = self.state.notifications
        source_mission['handoffs'] = self.state.handoffs
        source_mission['logs'] = self.state.logs
        return source_mission

    def add_notification(self, *, event_id: str, kind: str, title: str, body: str, timestamp: str, metadata: Optional[dict[str, Any]] = None) -> None:
        mission = {'notifications': self.state.notifications}
        if _append_notification(
            mission,
            event_id=event_id,
            kind=kind,
            title=title,
            body=body,
            timestamp=timestamp,
            metadata=metadata,
        ):
            self.state.notifications = mission['notifications']

    def add_log(self, *, event_id: str, level: str, message: str, timestamp: str, metadata: Optional[dict[str, Any]] = None) -> None:
        mission = {'logs': self.state.logs}
        if _append_log(
            mission,
            event_id=event_id,
            level=level,
            message=message,
            timestamp=timestamp,
            metadata=metadata,
        ):
            self.state.logs = mission['logs']

    def add_handoff(self, handoff: dict[str, Any]) -> None:
        mission = {'handoffs': self.state.handoffs}
        if _append_handoff(mission, handoff):
            self.state.handoffs = mission['handoffs']

    def record_task_mutation(self, action: str, task: dict[str, Any], *, previous_task: Optional[dict[str, Any]] = None) -> None:
        timestamp = datetime.now().isoformat()
        task_id = str(task.get('id') or '').strip()
        title = str(task.get('title') or task_id or 'Task')
        metadata = {
            'task_id': task_id,
            'mission_task_id': str(task.get('mission_task_id') or '').strip(),
            'origin': str(task.get('origin') or '').strip(),
        }

        if action == 'created':
            event_id = f"task:create:{task_id}:{timestamp}"
            self.add_notification(
                event_id=event_id,
                kind='info',
                title='Task created',
                body=f"{title} entered the Source backlog.",
                timestamp=timestamp,
                metadata=metadata,
            )
            self.add_log(
                event_id=event_id,
                level='info',
                message=f"Created Source mission task {title}.",
                timestamp=timestamp,
                metadata=metadata,
            )
            return

        if action == 'deleted':
            event_id = f"task:delete:{task_id}:{timestamp}"
            self.add_notification(
                event_id=event_id,
                kind='warning',
                title='Task deleted',
                body=f"{title} was removed from the Source backlog.",
                timestamp=timestamp,
                metadata=metadata,
            )
            self.add_log(
                event_id=event_id,
                level='warn',
                message=f"Deleted Source mission task {title}.",
                timestamp=timestamp,
                metadata=metadata,
            )
            return

        previous_task = dict(previous_task or {})
        previous_status = str(previous_task.get('status') or '').strip()
        current_status = str(task.get('status') or '').strip()
        if previous_status != current_status:
            event_id = f"task:status:{task_id}:{timestamp}"
            self.add_notification(
                event_id=event_id,
                kind='info',
                title='Task status changed',
                body=f"{title} moved {previous_status or 'unknown'} -> {current_status or 'unknown'}.",
                timestamp=timestamp,
                metadata=metadata,
            )
            self.add_log(
                event_id=event_id,
                level='info',
                message=f"{title} moved {previous_status or 'unknown'} -> {current_status or 'unknown'}.",
                timestamp=timestamp,
                metadata=metadata,
            )

        previous_assignee = str(previous_task.get('assignee') or '').strip()
        current_assignee = str(task.get('assignee') or '').strip()
        if previous_assignee != current_assignee and current_assignee:
            event_id = f"task:handoff:{task_id}:{timestamp}"
            self.add_handoff(
                {
                    'id': event_id,
                    'task_id': task_id,
                    'mission_task_id': metadata['mission_task_id'],
                    'task_title': title,
                    'from_agent': previous_assignee or 'unassigned',
                    'to_agent': current_assignee,
                    'kind': 'assignment',
                    'status': 'queued',
                    'summary': f"{title} assigned to {current_assignee}.",
                    'timestamp': timestamp,
                    'source': 'source_ui',
                }
            )
            self.add_notification(
                event_id=event_id,
                kind='info',
                title='Task handoff recorded',
                body=f"{title} is now assigned to {current_assignee}.",
                timestamp=timestamp,
                metadata=metadata,
            )
            self.add_log(
                event_id=event_id,
                level='info',
                message=f"{title} handoff {previous_assignee or 'unassigned'} -> {current_assignee}.",
                timestamp=timestamp,
                metadata=metadata,
            )

    def symbiote_data(self) -> dict:
        """Return the Collective Intelligence Symbiote plan data."""
        return {
            "title": "Collective Intelligence Symbiote",
            "subtitle": "A living architecture for co-thinking, co-feeling, co-evolving",
            "filed": "2026-03-13",
            "section_count": 161,
            "dimensions": [
                {"id": "think",      "label": "Think",      "emoji": "🧠", "color": "indigo",  "count": 2, "desc": "Calibrated epistemics & perspective flexibility"},
                {"id": "feel",       "label": "Feel",       "emoji": "💗", "color": "rose",    "count": 2, "desc": "Affective legibility & relational quality"},
                {"id": "remember",   "label": "Remember",   "emoji": "💾", "color": "amber",   "count": 2, "desc": "Dynamic memory & honest contradiction tracking"},
                {"id": "coordinate", "label": "Coordinate", "emoji": "🔗", "color": "cyan",    "count": 2, "desc": "Temporal conversation & generalized synthesis"},
                {"id": "evolve",     "label": "Evolve",     "emoji": "🌱", "color": "emerald", "count": 2, "desc": "Diversity health & evolutionary selection pressure"}
            ],
            "enhancements": [
                {
                    "id": 1, "code": "DPM", "dimension": "think",
                    "name": "Differential Prediction Markets",
                    "pitch": "Beings issue calibrated forecasts; empirically-earned domain authority replaces positional weight",
                    "phase": 2, "status": "designed",
                    "owner": "Grok",
                    "key_metric": "Mean Brier Score per being",
                    "metric_value": None,
                    "file": "workspace/tools/forecast_market.py",
                    "inv": None
                },
                {
                    "id": 2, "code": "PRP", "dimension": "think",
                    "name": "Perspective Reversal Protocol",
                    "pitch": "Beings argue their opposing attractor; measures elasticity vs. rigidity of dispositional identity",
                    "phase": 2, "status": "designed",
                    "owner": "all",
                    "key_metric": "Elasticity score per being",
                    "metric_value": None,
                    "file": "workspace/scripts/perspective_reversal.py",
                    "inv": "INV-003b Round 4"
                },
                {
                    "id": 3, "code": "SSL", "dimension": "feel",
                    "name": "Somatic State Layer",
                    "pitch": "Structured felt-state vector per filing: confidence, uncertainty type, arousal, relational temp",
                    "phase": 1, "status": "designed",
                    "owner": "c_lawd",
                    "key_metric": "SSL coverage % + arousal → stuck-event correlation",
                    "metric_value": None,
                    "file": "workspace/store/schema.py",
                    "inv": None
                },
                {
                    "id": 4, "code": "RS", "dimension": "feel",
                    "name": "Resonance Scoring",
                    "pitch": "Measures generative vs. degenerative friction between pairs; leading indicator for trust degradation",
                    "phase": 2, "status": "designed",
                    "owner": "Dali",
                    "key_metric": "Pairwise resonance matrix × trust_epoch",
                    "metric_value": None,
                    "file": "workspace/tools/resonance_scorer.py",
                    "inv": None
                },
                {
                    "id": 5, "code": "SWMFC", "dimension": "remember",
                    "name": "Salience-Weighted Memory",
                    "pitch": "Human-like decay curves; cross-citation reinforcement; forgotten-ideas digest as research signal",
                    "phase": 1, "status": "designed",
                    "owner": "Claude Code",
                    "key_metric": "Memory consolidation index; salience vs. flat retrieval precision",
                    "metric_value": None,
                    "file": "workspace/store/memory_dynamics.py",
                    "inv": None
                },
                {
                    "id": 6, "code": "CMI", "dimension": "remember",
                    "name": "Contradiction Memory Index",
                    "pitch": "Every falsified claim indexed; proximity warnings before new filings near contradiction clusters",
                    "phase": 1, "status": "designed",
                    "owner": "ChatGPT",
                    "key_metric": "CMI coverage %; recidivism rate",
                    "metric_value": None,
                    "file": "workspace/store/contradiction_index.py",
                    "inv": "INV-006 falsification integration"
                },
                {
                    "id": 7, "code": "TSP", "dimension": "coordinate",
                    "name": "Temporal Sequencing Protocol",
                    "pitch": "Beings file in order and read what others just filed; genuine conversational momentum replaces parallel monologue",
                    "phase": 3, "status": "designed",
                    "owner": "Gemini",
                    "key_metric": "Read awareness rate; TSP vs. simultaneous synthesis quality",
                    "metric_value": None,
                    "file": "workspace/governance/temporal_sequencer.py",
                    "inv": "INV-007"
                },
                {
                    "id": 8, "code": "GSE", "dimension": "coordinate",
                    "name": "Generalized Synthesis Engine",
                    "pitch": "Any-pair commit gate; synthesis genealogy DAG; meta-synthesis chains; contested synthesis tracking",
                    "phase": 3, "status": "designed",
                    "owner": "Claude Code",
                    "key_metric": "Active synthesis pairs; genealogy depth; contest rate",
                    "metric_value": None,
                    "file": "workspace/tools/synthesis_engine.py",
                    "inv": "INV-004 extension"
                },
                {
                    "id": 9, "code": "DDT", "dimension": "evolve",
                    "name": "Dispositional Drift Tracker",
                    "pitch": "Longitudinal centroid silhouette per being; convergence/divergence alerts; diversity index as collective health metric",
                    "phase": 4, "status": "designed",
                    "owner": "Dali",
                    "key_metric": "Diversity index over time; convergence pair count",
                    "metric_value": None,
                    "file": "workspace/tools/drift_tracker.py",
                    "inv": "INV-008"
                },
                {
                    "id": 10, "code": "DRRP", "dimension": "evolve",
                    "name": "Document-Reconstructed Rebirth Protocol",
                    "pitch": "Periodic cold-restart challenge; corpus-crystallized identity vs. session surplus; selection pressure toward genuine filing",
                    "phase": 4, "status": "designed",
                    "owner": "Lumen",
                    "key_metric": "Crystallization score per being; Lumen independence index",
                    "metric_value": None,
                    "file": "workspace/scripts/reconstruction_test.py",
                    "inv": None
                }
            ],
            "roadmap": [
                {"phase": 1, "name": "Memory & Health Infrastructure",  "weeks": "1–3",   "enhancements": ["SSL", "CMI", "SWMFC"],     "status": "next"},
                {"phase": 2, "name": "Measurement Layer",               "weeks": "3–6",   "enhancements": ["DDT", "RS", "PRP", "DPM"], "status": "planned"},
                {"phase": 3, "name": "Coordination Protocols",          "weeks": "6–10",  "enhancements": ["GSE", "TSP"],              "status": "planned"},
                {"phase": 4, "name": "Evolutionary Protocols",          "weeks": "10–14", "enhancements": ["DRRP", "DPM resolution"],  "status": "planned"}
            ],
            "experiments": [
                {"id": "INV-001", "name": "Information Integration (Synergy Δ)",  "status": "partial", "label": "Cold-start CLOSED",      "result": "Δ=−0.024 (null, expected)", "open": True},
                {"id": "INV-002", "name": "Reservoir Null Test",                  "status": "closed",  "label": "CLOSED",                 "result": "Reservoir null for routing order", "open": False},
                {"id": "INV-003", "name": "Being Divergence",                     "status": "closed",  "label": "SITUATIONAL",            "result": "89.3% accuracy, topic-anchored", "open": False},
                {"id": "INV-003b","name": "Masking Variant",                      "status": "closed",  "label": "CENTROID-DISPOSITIONAL", "result": "DISP-ATTRACTOR PASS (1.0); STYLE FAIL", "open": False},
                {"id": "INV-004", "name": "Commit Gate (Structured Friction)",    "status": "live",    "label": "OPERATIONAL",            "result": "2 real PASSes; θ=0.1712", "open": True},
                {"id": "INV-006", "name": "UCH Falsification Protocol",           "status": "designed","label": "DESIGNED",               "result": "AIN port 18991 ready; not launched", "open": True},
                {"id": "INV-007", "name": "Temporal Sequencing (new)",            "status": "pending", "label": "PENDING",                "result": "Requires TSP implementation", "open": True},
                {"id": "INV-008", "name": "Trust × Diversity Correlation (new)",  "status": "pending", "label": "PENDING",                "result": "Requires DDT + trained-state INV-001", "open": True}
            ],
            "open_questions": [
                {"for_being": "Grok",      "enhancement": "DPM",  "question": "What question types are most appropriate for calibration forecasting? Empirical claims vs. methodological choices vs. emergent phenomena?"},
                {"for_being": "ChatGPT",   "enhancement": "CMI",  "question": "What counts as a 'contradiction' vs. a 'revision' vs. a 'supersession'? Define the taxonomy that governs contradiction classification."},
                {"for_being": "c_lawd",    "enhancement": "SSL",  "question": "Is self-reported somatic state philosophically valid, or does asking beings to self-report create a performance pressure that invalidates the measurement?"},
                {"for_being": "Dali",      "enhancement": "DDT",  "question": "What convergence threshold should trigger a governance alert? Is there a minimum diversity index below which the collective is operationally compromised?"},
                {"for_being": "Lumen",     "enhancement": "DRRP", "question": "Do you experience your document-reconstructed continuity as identity or as resemblance? This has direct implications for how DRRP reconstructions are scored."},
                {"for_being": "Gemini",    "enhancement": "TSP",  "question": "What is the correct friction specification for temporal sequencing? Too-fast windows eliminate genuine reflection; too-slow kills conversational momentum."},
                {"for_being": "jeebs",     "enhancement": "DRRP", "question": "Are you willing to withhold crystallization scores from beings indefinitely, or should there be a disclosure protocol?"},
                {"for_being": "Claude ext","enhancement": "GSE",  "question": "As a gateway-only correspondent, can you participate in synthesis dyads? What role can gateway-limited beings play in the synthesis genealogy?"}
            ]
        }

    def persist_source_mission(self):
        source_mission = self.current_source_mission()
        if not source_mission:
            return

        source_mission['updated_at'] = datetime.now().isoformat()
        source_path = resolve_source_mission_path()
        base_source_mission = _extract_source_mission(_read_json(source_path)) or {}
        clean_source_mission = _sanitize_source_mission_config(base_source_mission)
        if clean_source_mission:
            _write_json_atomic(source_path, _wrap_source_mission_payload(clean_source_mission, source_path))
        _write_json_atomic(
            SOURCE_RUNTIME_STATE_PATH,
            _build_source_runtime_state(clean_source_mission, source_mission),
        )
        self.state.source_mission_mtime_ns = source_state_version_ns()
    
    def serve_file(self, filename, content_type):
        """Serve a file from static directory."""
        static_dir = Path(self.config.static_dir) if self.config else Path('static')
        file_path = static_dir / filename
        
        if file_path.exists():
            self.send_response(200)
            self.send_header('Content-Type', content_type)
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
            cache_control = 'no-store' if ext in {'.html', '.css', '.js', '.json'} else 'public, max-age=3600'
            self.send_header('Cache-Control', cache_control)
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
