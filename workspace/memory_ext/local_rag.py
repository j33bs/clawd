from __future__ import annotations

import hashlib
import json
import math
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from ._common import memory_ext_enabled, runtime_dir
except ImportError:  # pragma: no cover
    from _common import memory_ext_enabled, runtime_dir


def _tokenize(text: str) -> List[str]:
    return [tok for tok in str(text or "").lower().split() if tok]


class LocalEmbedder:
    def __init__(self, dim: int = 64):
        self.dim = int(dim)

    def _hash_embed(self, text: str) -> List[float]:
        tokens = _tokenize(text)
        vec = [0.0] * self.dim
        if not tokens:
            return vec
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(self.dim):
                vec[i] += (digest[i % len(digest)] / 255.0) - 0.5
        denom = float(len(tokens))
        return [v / denom for v in vec]

    def _coreml_embed(self, text: str) -> Optional[List[float]]:
        if os.getenv("OPENCLAW_COREML_EMBED", "0") != "1":
            return None
        cmd = os.getenv("OPENCLAW_COREML_EMBED_CMD", "")
        if not cmd:
            return None
        parts = shlex.split(cmd)
        if not parts or shutil.which(parts[0]) is None:
            return None
        try:
            proc = subprocess.run(parts + [text], capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                return None
            payload = json.loads(proc.stdout)
            emb = payload.get("embedding")
            if isinstance(emb, list) and len(emb) == self.dim:
                return [float(x) for x in emb]
        except Exception:
            return None
        return None

    def embed(self, text: str) -> List[float]:
        return self._coreml_embed(text) or self._hash_embed(text)


class LocalVectorDB:
    def __init__(self, index_path: Optional[Path] = None, manifest_path: Optional[Path] = None):
        self.index_path = index_path or runtime_dir("memory_ext", "rag_index.jsonl")
        self.manifest_path = manifest_path or runtime_dir("memory_ext", "rag_docs_manifest.jsonl")

    def add(self, doc: Dict[str, Any], embedder: Optional[LocalEmbedder] = None) -> Optional[Dict[str, Any]]:
        if not memory_ext_enabled():
            return None
        payload = dict(doc)
        text = str(payload.get("text", ""))
        if not payload.get("id"):
            payload["id"] = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        embedder = embedder or LocalEmbedder()
        payload["vector"] = embedder.embed(text)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")
        manifest_entry = {
            "id": payload.get("id"),
            "title": payload.get("title", ""),
            "source": payload.get("source", "local"),
        }
        with self.manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(manifest_entry, ensure_ascii=True, sort_keys=True) + "\n")
        return payload

    def load_all(self) -> List[Dict[str, Any]]:
        if not self.index_path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
        return rows


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def SemanticSearch(
    query: str,
    top_k: int = 5,
    db: Optional[LocalVectorDB] = None,
    embedder: Optional[LocalEmbedder] = None,
) -> List[Dict[str, Any]]:
    db = db or LocalVectorDB()
    embedder = embedder or LocalEmbedder()
    qvec = embedder.embed(query)
    scored: List[Dict[str, Any]] = []
    for row in db.load_all():
        vec = row.get("vector")
        if not isinstance(vec, list):
            continue
        sim = _cosine_similarity(qvec, [float(x) for x in vec])
        scored.append({"id": row.get("id"), "text": row.get("text", ""), "score": sim, "source": row.get("source", "local")})
    scored.sort(key=lambda x: (-float(x.get("score", 0.0)), str(x.get("id", ""))))
    return scored[: int(top_k)]


def rag_answer(
    question: str,
    context_limit: int = 3,
    db: Optional[LocalVectorDB] = None,
    embedder: Optional[LocalEmbedder] = None,
) -> Dict[str, Any]:
    results = SemanticSearch(question, top_k=context_limit, db=db, embedder=embedder)
    snippets = [str(item.get("text", "")).strip() for item in results if item.get("text")]
    if snippets:
        answer = " ".join(snippets[: int(context_limit)])
    else:
        answer = "No grounded context found in local RAG index."
    return {"answer": answer, "sources": results}


__all__ = ["LocalEmbedder", "LocalVectorDB", "SemanticSearch", "rag_answer"]
