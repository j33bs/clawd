from __future__ import annotations

import hashlib
import json
import os
import sys
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


class HiveMindStore:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or DEFAULT_BASE_DIR)
        self.data_dir = self.base_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.units_path = self.data_dir / "knowledge_units.jsonl"
        self.hash_index_path = self.data_dir / "hash_index.json"
        self.log_path = self.base_dir / "ingest.log"

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
        self.hash_index_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _append_jsonl(self, path: Path, record: Dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _log_ingest(self, record: Dict[str, Any]) -> None:
        entry = {
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            **record,
        }
        self._append_jsonl(self.log_path, entry)

    def all_units(self) -> List[Dict[str, Any]]:
        if not self.units_path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for line in self.units_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out

    def write_units(self, units: List[Dict[str, Any]]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self.units_path.open("w", encoding="utf-8") as fh:
            for unit in units:
                fh.write(json.dumps(unit, ensure_ascii=False) + "\n")

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
    def _score(cls, query: str, content: str) -> int:
        q_tokens = set(cls._tokenize(query))
        if not q_tokens:
            return 0
        c_tokens = set(cls._tokenize(content))
        score = len(q_tokens.intersection(c_tokens))
        if query.lower() in (content or "").lower():
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
        known = self._load_hashes()
        if digest in known:
            self._log_ingest({
                "event": "ingest_skip_dedup",
                "kind": ku.kind,
                "source": ku.source,
                "agent_scope": ku.agent_scope,
                "content_hash": digest,
            })
            return {"stored": False, "reason": "dedup", "content_hash": digest}

        record = ku.to_record(content=redacted, content_hash=digest)
        embedding = self._embed_redacted_text(redacted)
        if embedding is not None:
            record["embedding_model"] = DEFAULT_OLLAMA_EMBED_MODEL
            record["embedding"] = embedding
        self._append_jsonl(self.units_path, record)
        known.add(digest)
        self._save_hashes(known)
        self._log_ingest({
            "event": "ingest_store",
            "kind": ku.kind,
            "source": ku.source,
            "agent_scope": ku.agent_scope,
            "content_hash": digest,
        })
        return {"stored": True, "content_hash": digest, "record": record}

    def search(self, *, agent_scope: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        hits: List[Dict[str, Any]] = []
        touched_hashes: List[str] = []
        for unit in self.all_units():
            if self._is_expired(unit):
                continue
            if not self._can_view(agent_scope, str(unit.get("agent_scope", "shared"))):
                continue
            score = self._score(query, str(unit.get("content", "")))
            if score <= 0:
                continue
            item = dict(unit)
            item["score"] = score
            item["content"] = redact_for_embedding(str(item.get("content", "")))
            hits.append(item)
            if item.get("content_hash"):
                touched_hashes.append(str(item["content_hash"]))
        hits.sort(key=lambda x: (-int(x.get("score", 0)), str(x.get("created_at", ""))), reverse=False)
        self._record_access(touched_hashes)
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

    def _record_access(self, hashes: List[str]) -> None:
        if not hashes:
            return
        target = set(hashes)
        now = datetime.now(timezone.utc).isoformat()
        changed = False
        rows = self.all_units()
        for row in rows:
            digest = str(row.get("content_hash", ""))
            if digest not in target:
                continue
            row["access_count"] = int(row.get("access_count", 0)) + 1
            row["last_accessed_at"] = now
            changed = True
        if changed:
            self.write_units(rows)

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
