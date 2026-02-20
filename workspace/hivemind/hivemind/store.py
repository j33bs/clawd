from __future__ import annotations

import atexit
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import KnowledgeUnit
from .redaction import redact_for_embedding

TACTI_WORKSPACE = Path(__file__).resolve().parents[2]
if str(TACTI_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(TACTI_WORKSPACE))
try:
    from tacti_cr.semantic_immune import assess_content
except Exception:  # pragma: no cover
    assess_content = None

DEFAULT_BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"
DEFAULT_OLLAMA_EMBED_MODEL = "nomic-embed-text"
HASH_FLUSH_EVERY = 50
UNIT_TOKEN_LIMIT = 256
DEFAULT_UNITS_CACHE_TTL_SECONDS = 60.0


class HiveMindStore:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or DEFAULT_BASE_DIR)
        self.data_dir = self.base_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.units_path = self.data_dir / "knowledge_units.jsonl"
        self.hash_index_path = self.data_dir / "hash_index.json"
        self.access_log_path = self.data_dir / "access_log.jsonl"
        self.log_path = self.base_dir / "ingest.log"

        self._lock = threading.RLock()
        self._known_hashes: Optional[set[str]] = None
        self._hashes_dirty = False
        self._pending_hash_puts = 0

        self._units_cache: List[Dict[str, Any]] = []
        self._units_cache_loaded_at = 0.0
        self._units_cache_mtime_ns: Optional[int] = None
        self._units_cache_ttl_seconds = float(os.environ.get("HIVEMIND_UNITS_CACHE_TTL_SECONDS", DEFAULT_UNITS_CACHE_TTL_SECONDS))

        self._access_rollup_loaded = False
        self._access_rollup: Dict[str, Dict[str, Any]] = {}

        atexit.register(self.close)

    @staticmethod
    def content_hash(content: str) -> str:
        normalized = "\n".join(line.rstrip() for line in (content or "").strip().splitlines()).strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        buf = []
        acc = []
        for ch in (text or "").lower():
            if ch.isalnum() or ch in ("_", "-"):
                acc.append(ch)
            else:
                if acc:
                    buf.append("".join(acc))
                    acc = []
        if acc:
            buf.append("".join(acc))
        return buf

    @classmethod
    def _compact_tokens(cls, text: str, limit: int = UNIT_TOKEN_LIMIT) -> List[str]:
        tokens = sorted(set(cls._tokenize(text)))
        return tokens[: max(1, int(limit))]

    def _load_hashes(self) -> set[str]:
        if not self.hash_index_path.exists():
            return set()
        try:
            data = json.loads(self.hash_index_path.read_text(encoding="utf-8"))
        except Exception:
            return set()
        if not isinstance(data, list):
            return set()
        return set(str(x) for x in data)

    def _save_hashes(self, hashes: Iterable[str]) -> None:
        payload = sorted(set(hashes))
        self.hash_index_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(self.hash_index_path.parent)) as tmp:
            tmp.write(json.dumps(payload, indent=2) + "\n")
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, self.hash_index_path)

    def _ensure_hashes_loaded_locked(self) -> set[str]:
        if self._known_hashes is None:
            self._known_hashes = self._load_hashes()
        return self._known_hashes

    def _flush_hashes_locked(self, force: bool = False) -> None:
        if not self._hashes_dirty:
            return
        if not force and self._pending_hash_puts < HASH_FLUSH_EVERY:
            return
        self._save_hashes(self._known_hashes or set())
        self._hashes_dirty = False
        self._pending_hash_puts = 0

    def _append_jsonl(self, path: Path, record: Dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _log_ingest(self, record: Dict[str, Any]) -> None:
        entry = {
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            **record,
        }
        self._append_jsonl(self.log_path, entry)

    def _load_access_rollup_locked(self) -> None:
        if self._access_rollup_loaded:
            return
        self._access_rollup_loaded = True
        if not self.access_log_path.exists():
            return
        for line in self.access_log_path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except Exception:
                continue
            digest = str(row.get("content_hash", "")).strip()
            if not digest:
                continue
            state = self._access_rollup.setdefault(digest, {"count": 0, "last_accessed_at": ""})
            state["count"] = int(state.get("count", 0)) + 1
            ts = str(row.get("ts_utc", ""))
            if ts and ts > str(state.get("last_accessed_at", "")):
                state["last_accessed_at"] = ts

    def _load_units_locked(self, ttl_seconds: Optional[float] = None) -> List[Dict[str, Any]]:
        if not self.units_path.exists():
            self._units_cache = []
            self._units_cache_loaded_at = time.monotonic()
            self._units_cache_mtime_ns = None
            return []

        now = time.monotonic()
        ttl = self._units_cache_ttl_seconds if ttl_seconds is None else max(0.0, float(ttl_seconds))
        try:
            mtime_ns = int(self.units_path.stat().st_mtime_ns)
        except Exception:
            mtime_ns = None

        cache_fresh = (
            bool(self._units_cache)
            and self._units_cache_mtime_ns == mtime_ns
            and (now - self._units_cache_loaded_at) <= ttl
        )
        if cache_fresh:
            return self._units_cache

        out: List[Dict[str, Any]] = []
        for line in self.units_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
        self._units_cache = out
        self._units_cache_loaded_at = now
        self._units_cache_mtime_ns = mtime_ns
        return out

    def _apply_access_rollup(self, row: Dict[str, Any]) -> Dict[str, Any]:
        item = dict(row)
        digest = str(item.get("content_hash", "")).strip()
        access = self._access_rollup.get(digest)
        if access:
            item["access_count"] = int(item.get("access_count", 0)) + int(access.get("count", 0))
            last = str(item.get("last_accessed_at", "")).strip()
            rolled = str(access.get("last_accessed_at", "")).strip()
            if rolled and rolled > last:
                item["last_accessed_at"] = rolled
        return item

    def all_units(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._load_units_locked()
            self._load_access_rollup_locked()
            return [self._apply_access_rollup(row) for row in rows]

    def all_units_cached(self, ttl_seconds: float = 60.0) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._load_units_locked(ttl_seconds=float(ttl_seconds))
            self._load_access_rollup_locked()
            return [self._apply_access_rollup(row) for row in rows]

    def invalidate_units_cache(self) -> None:
        with self._lock:
            self._units_cache = []
            self._units_cache_loaded_at = 0.0
            self._units_cache_mtime_ns = None

    def write_units(self, units: List[Dict[str, Any]]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self.units_path.open("w", encoding="utf-8") as fh:
            for unit in units:
                fh.write(json.dumps(unit, ensure_ascii=False) + "\n")
        with self._lock:
            self._units_cache = [dict(unit) for unit in units]
            self._units_cache_loaded_at = time.monotonic()
            try:
                self._units_cache_mtime_ns = int(self.units_path.stat().st_mtime_ns)
            except Exception:
                self._units_cache_mtime_ns = None

    def close(self) -> None:
        with self._lock:
            self._flush_hashes_locked(force=True)

    @staticmethod
    def _is_expired(unit: Dict[str, Any]) -> bool:
        expires_at = unit.get("expires_at")
        if not expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(str(expires_at))
        except Exception:
            return False
        now = datetime.now(timezone.utc)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return now >= expiry

    @staticmethod
    def _can_view(agent_scope: str, item_scope: str) -> bool:
        if item_scope == "shared":
            return True
        return agent_scope == item_scope

    @classmethod
    def _score(cls, q_tokens: set[str], query_lower: str, content: str, tokens: Optional[List[str]] = None) -> int:
        if not q_tokens:
            return 0
        c_tokens = set(tokens or cls._tokenize(content))
        score = len(q_tokens.intersection(c_tokens))
        if query_lower and query_lower in (content or "").lower():
            score += 3
        return score

    def put(self, ku: KnowledgeUnit, content: str) -> Dict[str, Any]:
        redacted = redact_for_embedding(content)
        if callable(assess_content):
            immune = assess_content(self.base_dir.parents[1], redacted)
            if immune.get("quarantined"):
                self._log_ingest(
                    {
                        "event": "ingest_quarantine_semantic_immune",
                        "kind": ku.kind,
                        "source": ku.source,
                        "agent_scope": ku.agent_scope,
                        "content_hash": immune.get("content_hash"),
                        "score": immune.get("score"),
                        "threshold": immune.get("threshold"),
                    }
                )
                return {
                    "stored": False,
                    "reason": "semantic_quarantine",
                    "content_hash": immune.get("content_hash"),
                }

        digest = self.content_hash(redacted)
        with self._lock:
            known = self._ensure_hashes_loaded_locked()
            if digest in known:
                self._log_ingest(
                    {
                        "event": "ingest_skip_dedup",
                        "kind": ku.kind,
                        "source": ku.source,
                        "agent_scope": ku.agent_scope,
                        "content_hash": digest,
                    }
                )
                return {"stored": False, "reason": "dedup", "content_hash": digest}

            record = ku.to_record(content=redacted, content_hash=digest)
            record["tokens"] = self._compact_tokens(redacted)
            embedding = self._embed_redacted_text(redacted)
            if embedding is not None:
                record["embedding_model"] = DEFAULT_OLLAMA_EMBED_MODEL
                record["embedding"] = embedding
            self._append_jsonl(self.units_path, record)
            known.add(digest)
            self._hashes_dirty = True
            self._pending_hash_puts += 1
            self._flush_hashes_locked(force=False)
            self._units_cache.append(dict(record))
            self._units_cache_loaded_at = time.monotonic()
            try:
                self._units_cache_mtime_ns = int(self.units_path.stat().st_mtime_ns)
            except Exception:
                self._units_cache_mtime_ns = None

        self._log_ingest(
            {
                "event": "ingest_store",
                "kind": ku.kind,
                "source": ku.source,
                "agent_scope": ku.agent_scope,
                "content_hash": digest,
            }
        )
        return {"stored": True, "content_hash": digest, "record": record}

    def search(self, *, agent_scope: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        q_tokens = set(self._tokenize(query))
        query_lower = (query or "").lower()
        hits: List[Dict[str, Any]] = []
        touched_hashes: List[str] = []
        for unit in self.all_units():
            if self._is_expired(unit):
                continue
            if not self._can_view(agent_scope, str(unit.get("agent_scope", "shared"))):
                continue
            content = str(unit.get("content", ""))
            unit_tokens = unit.get("tokens")
            if not isinstance(unit_tokens, list):
                unit_tokens = self._compact_tokens(content)
            score = self._score(q_tokens, query_lower, content, tokens=unit_tokens)
            if score <= 0:
                continue
            item = dict(unit)
            item["score"] = score
            item["content"] = redact_for_embedding(str(item.get("content", "")))
            hits.append(item)
            if item.get("content_hash"):
                touched_hashes.append(str(item["content_hash"]))
        hits.sort(key=lambda x: (-int(x.get("score", 0)), str(x.get("created_at", ""))), reverse=False)
        self._record_access(touched_hashes, query=query)
        return hits[: max(1, int(limit))]

    def log_event(self, event: str, **detail: Any) -> None:
        self._log_ingest({"event": event, **detail})

    def read_log(self) -> List[Dict[str, Any]]:
        if not self.log_path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out

    def _record_access(self, hashes: List[str], query: str = "") -> None:
        if not hashes:
            return
        now = datetime.now(timezone.utc).isoformat()
        unique: List[str] = []
        seen = set()
        for digest in hashes:
            value = str(digest).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            unique.append(value)
        if not unique:
            return
        with self.access_log_path.open("a", encoding="utf-8") as fh:
            for digest in unique:
                fh.write(json.dumps({"ts_utc": now, "content_hash": digest, "query": query}, ensure_ascii=False) + "\n")
        with self._lock:
            self._load_access_rollup_locked()
            for digest in unique:
                row = self._access_rollup.setdefault(digest, {"count": 0, "last_accessed_at": now})
                row["count"] = int(row.get("count", 0)) + 1
                row["last_accessed_at"] = now

    def _embed_redacted_text(self, text: str) -> Optional[List[float]]:
        if os.environ.get("HIVEMIND_ENABLE_OLLAMA_EMBEDDINGS", "0") != "1":
            return None

        url = os.environ.get("HIVEMIND_OLLAMA_EMBED_URL", DEFAULT_OLLAMA_EMBED_URL)
        parsed = urllib.parse.urlparse(url)
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            return None

        payload = json.dumps({"model": DEFAULT_OLLAMA_EMBED_MODEL, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError):
            return None

        try:
            data = json.loads(raw)
        except Exception:
            return None

        values = data.get("embedding")
        if not isinstance(values, list):
            return None
        out: List[float] = []
        for item in values:
            if isinstance(item, (int, float)):
                out.append(float(item))
        return out
