#!/usr/bin/env python3
"""Canonical c_lawd conversational kernel loader for surface adapters."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
KERNEL_PATH = REPO_ROOT / "nodes" / "c_lawd" / "CONVERSATION_KERNEL.md"
USER_PATH = REPO_ROOT / "USER.md"
MEMORY_PATH = REPO_ROOT / "MEMORY.md"


@dataclass(frozen=True)
class SurfaceKernelPacket:
    kernel_id: str
    kernel_hash: str
    surface_overlay: str
    prompt_text: str


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace").strip()


def _surface_overlay(*, surface: str, include_memory: bool, mode: str) -> tuple[str, str]:
    normalized_surface = surface.strip().lower() or "unknown"
    normalized_mode = mode.strip().lower() or "conversation"
    memory_mode = "memory:on" if include_memory else "memory:off"
    overlay_id = f"surface:{normalized_surface}|mode:{normalized_mode}|{memory_mode}"
    overlay_text = (
        "## Active surface\n\n"
        f"- surface: {normalized_surface}\n"
        f"- mode: {normalized_mode}\n"
        f"- memory: {'included' if include_memory else 'excluded'}\n"
        "- response goal: Codex-direct quality adapted to chat constraints\n"
        "- keep file/path references explicit when repo-grounded\n"
        "- make execution state and residual uncertainty concrete\n"
    )
    return overlay_id, overlay_text


@lru_cache(maxsize=32)
def build_c_lawd_surface_kernel_packet(
    *, surface: str = "telegram", include_memory: bool = True, mode: str = "conversation"
) -> SurfaceKernelPacket:
    parts: list[str] = []

    kernel = _read_text(KERNEL_PATH)
    if kernel:
        parts.append(kernel)

    user_profile = _read_text(USER_PATH)
    if user_profile:
        parts.append("## USER profile\n\n" + user_profile)

    if include_memory:
        memory = _read_text(MEMORY_PATH)
        if memory:
            parts.append("## MEMORY\n\n" + memory)

    overlay_id, overlay_text = _surface_overlay(
        surface=surface,
        include_memory=include_memory,
        mode=mode,
    )
    parts.append(overlay_text)

    prompt_text = "\n\n".join(part for part in parts if part).strip()
    return SurfaceKernelPacket(
        kernel_id=f"c_lawd:{overlay_id}",
        kernel_hash=hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        surface_overlay=overlay_id,
        prompt_text=prompt_text,
    )


@lru_cache(maxsize=16)
def build_c_lawd_surface_kernel(
    *, surface: str = "telegram", include_memory: bool = True, mode: str = "conversation"
) -> str:
    return build_c_lawd_surface_kernel_packet(
        surface=surface,
        include_memory=include_memory,
        mode=mode,
    ).prompt_text


__all__ = [
    "SurfaceKernelPacket",
    "build_c_lawd_surface_kernel",
    "build_c_lawd_surface_kernel_packet",
    "KERNEL_PATH",
    "USER_PATH",
    "MEMORY_PATH",
]
