from __future__ import annotations

import hashlib
import importlib
import os
import threading
from typing import Any

import numpy as np

CANONICAL_MODEL_ID = "mlx-community/answerdotai-ModernBERT-base-4bit"
ACCEL_MODEL_ID = "mlx-community/all-MiniLM-L6-v2-4bit"

MODEL_DIMS: dict[str, int] = {
    CANONICAL_MODEL_ID: 768,
    ACCEL_MODEL_ID: 384,
}

_MODEL_CACHE: dict[tuple[str, str], Any] = {}
_MODEL_CACHE_LOCK = threading.Lock()


def _backend_mode() -> str:
    return os.getenv("OPENCLAW_KB_EMBEDDINGS_BACKEND", "mlx").strip().lower()


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, ord=2, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


def _mock_embed(text: str, dim: int) -> list[float]:
    vec = np.zeros(dim, dtype=np.float32)
    tokens = [tok for tok in str(text or "").lower().split() if tok]
    if not tokens:
        return vec.tolist()
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(dim):
            vec[i] += (digest[i % len(digest)] / 255.0) - 0.5
    vec /= float(len(tokens))
    return vec.tolist()


def _load_mlx_model(model_id: str) -> Any:
    module = importlib.import_module("mlx_embeddings")

    if hasattr(module, "load"):
        return module.load(model_id)

    if hasattr(module, "EmbeddingModel"):
        cls = getattr(module, "EmbeddingModel")
        if hasattr(cls, "from_pretrained"):
            return cls.from_pretrained(model_id)
        return cls(model_id)

    if hasattr(module, "Model"):
        cls = getattr(module, "Model")
        if hasattr(cls, "from_pretrained"):
            return cls.from_pretrained(model_id)
        return cls(model_id)

    raise RuntimeError("Unsupported mlx_embeddings API: unable to load embedding model")


def _run_mlx_embed(model: Any, texts: list[str]) -> Any:
    if hasattr(model, "embed_batch"):
        return model.embed_batch(texts)
    if hasattr(model, "embed"):
        try:
            return model.embed(texts)
        except Exception:
            vectors = [model.embed(t) for t in texts]
            return vectors
    if hasattr(model, "encode"):
        return model.encode(texts)
    raise RuntimeError("Unsupported mlx embedding model: missing embed/encode method")


def _coerce_matrix(raw: Any, expected_rows: int) -> np.ndarray:
    arr = np.asarray(raw, dtype=np.float32)

    if arr.ndim == 1:
        arr = arr.reshape(1, -1)

    if arr.ndim != 2:
        if isinstance(raw, list):
            rows = [np.asarray(item, dtype=np.float32).reshape(-1) for item in raw]
            arr = np.stack(rows, axis=0)
        else:
            raise RuntimeError("Embedding backend returned unsupported shape")

    if arr.shape[0] != expected_rows:
        raise RuntimeError(
            f"Embedding backend returned {arr.shape[0]} rows for {expected_rows} texts"
        )
    return arr


class MlxEmbedder:
    """MLX embedding driver with per-model singleton cache and optional normalization."""

    def __init__(self, model_id: str, normalize: bool = True):
        if model_id not in MODEL_DIMS:
            raise ValueError(f"Unsupported model_id: {model_id}")
        self.model_id = model_id
        self.normalize = bool(normalize)
        self.dim = MODEL_DIMS[model_id]
        self.batch_size = max(1, int(os.getenv("OPENCLAW_KB_EMBED_BATCH_SIZE", "32")))
        self._mode = _backend_mode()
        self._backend = self._get_backend(model_id=model_id, mode=self._mode)

    @classmethod
    def _get_backend(cls, model_id: str, mode: str) -> Any:
        key = (mode, model_id)
        with _MODEL_CACHE_LOCK:
            if key in _MODEL_CACHE:
                return _MODEL_CACHE[key]
            if mode == "mock":
                _MODEL_CACHE[key] = {"mode": "mock", "dim": MODEL_DIMS[model_id]}
            else:
                _MODEL_CACHE[key] = _load_mlx_model(model_id)
            return _MODEL_CACHE[key]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list):
            raise TypeError("texts must be a list[str]")
        if not texts:
            return []

        vectors: list[np.ndarray] = []
        for idx in range(0, len(texts), self.batch_size):
            batch = [str(t) for t in texts[idx : idx + self.batch_size]]
            if self._mode == "mock":
                arr = np.asarray([_mock_embed(t, self.dim) for t in batch], dtype=np.float32)
            else:
                raw = _run_mlx_embed(self._backend, batch)
                arr = _coerce_matrix(raw, expected_rows=len(batch))

            if arr.shape[1] != self.dim:
                raise RuntimeError(
                    f"Embedding dimension mismatch for {self.model_id}: "
                    f"expected {self.dim}, got {arr.shape[1]}"
                )
            vectors.append(arr)

        matrix = np.vstack(vectors).astype(np.float32)
        if self.normalize:
            matrix = _normalize_rows(matrix)
        return matrix.tolist()
