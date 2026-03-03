"""Embedding drivers for knowledge base indexing and retrieval."""

from .driver_mlx import ACCEL_MODEL_ID, CANONICAL_MODEL_ID, MlxEmbedder

__all__ = ["MlxEmbedder", "CANONICAL_MODEL_ID", "ACCEL_MODEL_ID"]
