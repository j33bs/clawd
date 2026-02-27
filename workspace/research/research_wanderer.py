#!/usr/bin/env python3
"""
Research Wanderer - A research agent that keeps exploring between sessions.
Drift-friendly: runs in background, accumulates findings, surfaces new questions.

Usage:
  python3 research_wanderer.py add "topic to research"
  python3 research_wanderer.py wander    # Do research on queued topics
  python3 research_wanderer.py queue      # Show pending topics
  python3 research_wanderer.py status      # Show recent findings
"""

import os
import json
import sys
import fcntl
import hashlib
import re
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
WORKSPACE_DIR = SCRIPT_DIR.parent
GOVERNANCE_DIR = WORKSPACE_DIR / "governance"
QUEUE_FILE = SCRIPT_DIR / "queue.json"
FINDINGS_FILE = SCRIPT_DIR / "findings.json"
LOG_FILE = SCRIPT_DIR / "wander_log.md"
OPEN_QUESTIONS_FILE = GOVERNANCE_DIR / "OPEN_QUESTIONS.md"
OPEN_QUESTIONS_INDEX_FILE = GOVERNANCE_DIR / "OPEN_QUESTIONS_INDEX.md"
OPEN_QUESTIONS_SHARDS_DIR = GOVERNANCE_DIR / "open_questions_shards"
OPEN_QUESTIONS_LOCK_FILE = GOVERNANCE_DIR / ".open_questions.lock"


def _env_int(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


MAX_QUESTIONS_PER_RUN = _env_int("RESEARCH_WANDERER_MAX_QUESTIONS_PER_RUN", 1, 1)
QUESTION_COOLDOWN_HOURS = _env_int("RESEARCH_WANDERER_APPEND_COOLDOWN_HOURS", 6, 0)
QUESTION_DEDUPE_DAYS = _env_int("RESEARCH_WANDERER_DEDUPE_DAYS", 14, 1)
QUESTION_STATE_TTL_DAYS = _env_int("RESEARCH_WANDERER_STATE_TTL_DAYS", 90, 7)
OPEN_QUESTIONS_LOCK_TIMEOUT_SEC = _env_int("RESEARCH_WANDERER_LOCK_TIMEOUT_SEC", 5, 1)

DEFAULT_TOPICS = [
    "predictive processing vs next token prediction",
    "AI consciousness measurement integrated information",
    "multi-agent collective cognition emergence",
    "LLM world models internal representations",
    "embodied cognition symbol grounding AI",
    "AI memory consolidation sleep replay",
    "distributed AI identity continuity",
    "alien intelligence detection framework",
]

def load_queue():
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE) as f:
            return json.load(f)
    return {"topics": DEFAULT_TOPICS, "completed": [], "last_wander": None}

def _quiesced() -> bool:
    return os.getenv("OPENCLAW_QUIESCE") == "1"


def _skip_quiesced_write(path: Path) -> bool:
    if not _quiesced():
        return False
    print(f"QUIESCED: skipping write to {path}")
    return True


def save_queue(q):
    if _skip_quiesced_write(QUEUE_FILE):
        return
    with open(QUEUE_FILE, "w") as f:
        json.dump(q, f, indent=2)

def load_findings():
    if FINDINGS_FILE.exists():
        with open(FINDINGS_FILE) as f:
            return json.load(f)
    return {"findings": [], "questions_generated": [], "open_questions_state": {}}

def save_findings(findings):
    if _skip_quiesced_write(FINDINGS_FILE):
        return
    with open(FINDINGS_FILE, "w") as f:
        json.dump(findings, f, indent=2)

def add_topic(topic):
    q = load_queue()
    if topic not in q["topics"] and topic not in q["completed"]:
        q["topics"].append(topic)
        save_queue(q)
        print(f"✅ Added: {topic}")
    else:
        print(f"📝 Already in queue: {topic}")

def show_queue():
    q = load_queue()
    print("\n📚 Research Queue:")
    for i, t in enumerate(q["topics"], 1):
        print(f"  {i}. {t}")
    if q["completed"]:
        print(f"\n✅ Completed ({len(q['completed'])}):")
        for t in q["completed"][-5:]:
            print(f"  • {t}")

def show_status():
    f = load_findings()
    q = load_queue()
    print(f"\n🧠 Research Wanderer Status")
    print(f"   Topics in queue: {len(q['topics'])}")
    print(f"   Topics completed: {len(q['completed'])}")
    print(f"   Findings recorded: {len(f['findings'])}")
    print(f"   Questions generated: {len(f['questions_generated'])}")
    if q["last_wander"]:
        print(f"   Last wander: {q['last_wander']}")
    
    if f["findings"]:
        print(f"\n📡 Recent findings:")
        for finding in f["findings"][-3:]:
            print(f"  - {finding[:100]}...")

def log_wander(content):
    if _skip_quiesced_write(LOG_FILE):
        return
    with open(LOG_FILE, "a") as f:
        f.write(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{content}\n\n---\n\n")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", StringOrEmpty(question).strip().lower())


def _question_hash(question: str, source_topic: str = "") -> str:
    normalized = _normalize_question(question)
    source = _normalize_question(source_topic)
    payload = f"{normalized}|source:{source}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def StringOrEmpty(value) -> str:
    return value if isinstance(value, str) else ""


@contextmanager
def _exclusive_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as lock_file:
        deadline = time.monotonic() + OPEN_QUESTIONS_LOCK_TIMEOUT_SEC
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    print(
                        "OPEN_QUESTIONS_LOCK_TIMEOUT "
                        f"path={OPEN_QUESTIONS_FILE} lock={lock_path} "
                        f"seconds={OPEN_QUESTIONS_LOCK_TIMEOUT_SEC}",
                        file=sys.stderr,
                    )
                    raise TimeoutError("open_questions_lock_timeout")
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _append_line(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = text.rstrip("\n") + "\n"
    with open(path, "a+", encoding="utf-8") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() > 0:
            handle.write("\n")
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def ensure_open_questions_index():
    if OPEN_QUESTIONS_INDEX_FILE.exists():
        return
    body = (
        "# OPEN_QUESTIONS Index\n\n"
        "- Canonical narrative log: `OPEN_QUESTIONS.md` (append-only; not rewritten).\n"
        "- Operational mirror shards: `open_questions_shards/YYYY-MM.md`.\n"
        "- New Research Wanderer entries are dual-written to canonical + current-month shard.\n"
        "- No historical content is migrated out of canonical.\n"
    )
    _append_line(OPEN_QUESTIONS_INDEX_FILE, body)


def append_open_question_entry(question: str, source_topic: str, timestamp_utc: datetime):
    if _skip_quiesced_write(OPEN_QUESTIONS_FILE):
        return False

    ensure_open_questions_index()
    month_key = timestamp_utc.strftime("%Y-%m")
    shard_path = OPEN_QUESTIONS_SHARDS_DIR / f"{month_key}.md"
    stamp = timestamp_utc.strftime("%Y-%m-%d %H:%M UTC")
    entry = (
        f"### {stamp} — Research Wanderer\n"
        f"- Question: {question}\n"
        f"- Source topic: {source_topic}\n"
        "- Tag: EXPERIMENT PENDING\n"
        "- Note: additive append only (canonical + shard mirror)\n"
    )
    with _exclusive_lock(OPEN_QUESTIONS_LOCK_FILE):
        _append_line(OPEN_QUESTIONS_FILE, entry)
        _append_line(shard_path, entry)
    return True


def _prune_question_state(state: dict, now_utc: datetime):
    dedupe = state.get("dedupe", {})
    if not isinstance(dedupe, dict):
        state["dedupe"] = {}
        return
    cutoff = now_utc - timedelta(days=QUESTION_STATE_TTL_DAYS)
    keep = {}
    for qhash, ts in dedupe.items():
        parsed = _parse_iso_utc(StringOrEmpty(ts))
        if parsed and parsed >= cutoff:
            keep[qhash] = parsed.isoformat()
    dedupe.clear()
    dedupe.update(keep)


def maybe_append_open_question(findings: dict, question: str, source_topic: str, now_utc: datetime):
    state = findings.setdefault("open_questions_state", {})
    if not isinstance(state, dict):
        state = {}
        findings["open_questions_state"] = state
    dedupe = state.setdefault("dedupe", {})
    if not isinstance(dedupe, dict):
        dedupe = {}
        state["dedupe"] = dedupe

    _prune_question_state(state, now_utc)
    dedupe = state.get("dedupe", {})
    if not isinstance(dedupe, dict):
        dedupe = {}
        state["dedupe"] = dedupe
    qhash = _question_hash(question, source_topic)
    last_seen = _parse_iso_utc(StringOrEmpty(dedupe.get(qhash)))
    if last_seen and now_utc - last_seen < timedelta(days=QUESTION_DEDUPE_DAYS):
        return False, "duplicate_recent"

    last_append_ts = _parse_iso_utc(StringOrEmpty(state.get("last_append_ts")))
    if last_append_ts and now_utc - last_append_ts < timedelta(hours=QUESTION_COOLDOWN_HOURS):
        return False, "cooldown_active"

    try:
        appended = append_open_question_entry(question, source_topic, now_utc)
    except TimeoutError:
        return False, "lock_timeout"
    if not appended:
        return False, "quiesced"

    now_iso = now_utc.isoformat()
    dedupe[qhash] = now_iso
    state["last_append_ts"] = now_iso
    return True, "appended"


def append_test(target: str | None = None):
    now_utc = _utc_now()
    target_path = Path(target) if target else Path("/tmp/open_questions_append_test.md")
    sentinel = f"<!-- APPEND_TEST {now_utc.isoformat()} -->"
    lock_path = target_path.parent / f".{target_path.name}.lock"
    with _exclusive_lock(lock_path):
        _append_line(target_path, sentinel)
    print(f"APPEND_TEST_OK target={target_path}")

def main():
    if len(sys.argv) < 2:
        show_status()
        return
    
    cmd = sys.argv[1]
    
    if cmd == "add":
        if len(sys.argv) < 3:
            print("Usage: research_wanderer.py add 'topic'")
            sys.exit(1)
        add_topic(sys.argv[2])
    
    elif cmd == "queue":
        show_queue()
    
    elif cmd == "status":
        show_status()
    
    elif cmd == "wander":
        q = load_queue()
        if not q["topics"]:
            print("No topics to research. Add some!")
            sys.exit(1)
        
        topic = q["topics"][0]
        print(f"Wandering: {topic}")
        
        # Mark as explored (in real impl, would do actual research here)
        q["topics"].pop(0)
        q["completed"].append(topic)
        q["last_wander"] = datetime.now().isoformat()
        
        # Generate a placeholder finding (would be web search in full impl)
        finding = f"Explored: {topic}"
        
        f = load_findings()
        f["findings"].append({
            "topic": topic,
            "finding": finding,
            "timestamp": datetime.now().isoformat()
        })
        
        # Generate new question
        new_q = f"What would {topic} mean for TACTI(C)-R?"
        f["questions_generated"].append({
            "question": new_q,
            "from_topic": topic,
            "timestamp": datetime.now().isoformat()
        })

        now_utc = _utc_now()
        append_result = None
        append_reason = None
        for candidate in [new_q][:MAX_QUESTIONS_PER_RUN]:
            append_result, append_reason = maybe_append_open_question(f, candidate, topic, now_utc)
            if append_result:
                break
        
        save_queue(q)
        save_findings(f)
        
        append_status = "appended" if append_result else f"skipped ({append_reason})"
        log_wander(f"Wandered: {topic}\n\nGenerated question: {new_q}\nOpen questions append: {append_status}")
        
        print(f"✅ Wandered: {topic}")
        print(f"   New question: {new_q}")
        print(f"   Open questions append: {append_status}")
    
    elif cmd == "init":
        q = load_queue()
        if not q["topics"]:
            q["topics"] = DEFAULT_TOPICS
            save_queue(q)
            print("✅ Initialized with default topics")
        else:
            print("Queue already initialized")

    elif cmd == "append-test":
        target = sys.argv[2] if len(sys.argv) > 2 else None
        append_test(target)
    
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: add, queue, status, wander, init, append-test")

if __name__ == "__main__":
    main()
