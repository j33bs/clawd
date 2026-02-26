#!/usr/bin/env python3
"""Embedding interface for Telegram vector pipeline (local-first)."""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Sequence


def l2_normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values))
    if norm <= 0:
        return [0.0 for _ in values]
    return [v / norm for v in values]


def cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    if len(vec_a) != len(vec_b):
        raise ValueError("dimension mismatch")
    a = l2_normalize([float(x) for x in vec_a])
    b = l2_normalize([float(x) for x in vec_b])
    return sum(x * y for x, y in zip(a, b))


class Embedder:
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class DeterministicHashEmbedder(Embedder):
    dim: int = 8
    name: str = "deterministic-hash-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            values: list[float] = []
            for idx in range(self.dim):
                byte = digest[idx % len(digest)]
                signed = (byte - 127.5) / 127.5
                values.append(float(signed))
            vectors.append(l2_normalize(values))
        return vectors


@dataclass
class KeywordStubEmbedder(Embedder):
    dim: int = 64
    name: str = "keyword-stub-v1"

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0 for _ in range(self.dim)]
            for token in self._tokenize(text):
                digest = hashlib.sha1(token.encode("utf-8")).digest()
                bucket = int.from_bytes(digest[:2], "big") % self.dim
                vec[bucket] += 1.0
            vectors.append(l2_normalize(vec))
        return vectors


@dataclass
class OllamaEmbedder(Embedder):
    model: str = "nomic-embed-text"
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 30.0
    name: str = "ollama:nomic-embed-text"
    dim: int = 0

    def _post_json(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}{path}",
            method="POST",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)

    def _embed_batch_modern(self, texts: list[str]) -> list[list[float]]:
        data = self._post_json("/api/embed", {"model": self.model, "input": texts})
        vectors = data.get("embeddings")
        if not isinstance(vectors, list):
            raise ValueError("ollama /api/embed returned invalid embeddings")
        out = [[float(x) for x in row] for row in vectors]
        if out and self.dim <= 0:
            self.dim = len(out[0])
        return out

    def _embed_batch_legacy(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            data = self._post_json("/api/embeddings", {"model": self.model, "prompt": text})
            vector = data.get("embedding")
            if not isinstance(vector, list):
                raise ValueError("ollama /api/embeddings returned invalid embedding")
            out.append([float(x) for x in vector])
        if out and self.dim <= 0:
            self.dim = len(out[0])
        return out

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            return self._embed_batch_modern(texts)
        except Exception:
            return self._embed_batch_legacy(texts)


@dataclass
class SentenceTransformersEmbedder(Embedder):
    model: str = "all-MiniLM-L6-v2"
    name: str = "sentence-transformers:all-MiniLM-L6-v2"
    dim: int = 0

    def __post_init__(self):
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._model = SentenceTransformer(self.model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, show_progress_bar=False)
        out = [[float(x) for x in row] for row in vectors]
        if out and self.dim <= 0:
            self.dim = len(out[0])
        return out


def build_embedder(name: str | None = None) -> Embedder:
    chosen = (name or "").strip().lower()
    if not chosen:
        chosen = "auto"

    if chosen in {"auto", "ollama"}:
        try:
            embedder = OllamaEmbedder()
            probe = embedder.embed(["probe"])
            if probe and probe[0]:
                return embedder
        except Exception:
            if chosen == "ollama":
                raise
    if chosen in {"auto", "minilm", "sentence-transformers"}:
        try:
            embedder = SentenceTransformersEmbedder()
            probe = embedder.embed(["probe"])
            if probe and probe[0]:
                return embedder
        except Exception:
            if chosen in {"minilm", "sentence-transformers"}:
                raise
    if chosen in {"auto", "keyword_stub", "stub"}:
        return KeywordStubEmbedder()
    if chosen in {"deterministic_hash", "hash_stub"}:
        return DeterministicHashEmbedder()
    return KeywordStubEmbedder()
