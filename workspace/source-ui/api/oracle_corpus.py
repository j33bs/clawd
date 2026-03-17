"""Source UI Oracle corpus assembly and lightweight lexical retrieval."""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


logger = logging.getLogger("source-ui.oracle")

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT / "workspace"
SOURCE_UI_ROOT = WORKSPACE_ROOT / "source-ui"

ORACLE_CORRESPONDENCE_PATH = WORKSPACE_ROOT / "governance" / "OPEN_QUESTIONS.md"
ORACLE_GRAPH_PATH = WORKSPACE_ROOT / "knowledge_base" / "data" / "graph.jsonl"
ORACLE_RESEARCH_IMPORT_PATH = WORKSPACE_ROOT / "knowledge_base" / "data" / "research_import.jsonl"
ORACLE_RESEARCH_PAPERS_PATH = WORKSPACE_ROOT / "research" / "data" / "papers.jsonl"
ORACLE_USER_INFERENCES_PATH = WORKSPACE_ROOT / "knowledge_base" / "data" / "user_inferences.jsonl"
ORACLE_PREFERENCE_PROFILE_PATH = WORKSPACE_ROOT / "knowledge_base" / "data" / "preference_profile.json"
ORACLE_RESEARCH_DOC_ROOT = WORKSPACE_ROOT / "research"
ORACLE_MEMORY_SOURCES = (
    ("telegram_memory", WORKSPACE_ROOT / "knowledge_base" / "data" / "telegram_messages.jsonl", 450),
    ("discord_memory", WORKSPACE_ROOT / "knowledge_base" / "data" / "discord_messages.jsonl", 200),
    ("discord_research", WORKSPACE_ROOT / "knowledge_base" / "data" / "discord_research_messages.jsonl", 120),
)
ORACLE_CORE_DOC_PATHS = (
    WORKSPACE_ROOT / "SOUL.md",
    WORKSPACE_ROOT / "USER.md",
    WORKSPACE_ROOT / "MEMORY.md",
    WORKSPACE_ROOT / "SYSTEM_STATUS.md",
    WORKSPACE_ROOT / "GOALS.md",
    WORKSPACE_ROOT / "CONSTITUTION.md",
    WORKSPACE_ROOT / "MODEL_ROUTING.md",
    WORKSPACE_ROOT / "TOOLS.md",
)
ORACLE_PROJECT_INDEX_ROOTS = (
    ("Source UI", WORKSPACE_ROOT / "source-ui", {".py", ".js", ".css", ".html", ".json", ".md"}, 180),
    ("Workspace Scripts", WORKSPACE_ROOT / "scripts", {".py", ".sh", ".md", ".json"}, 120),
    ("Repo Scripts", REPO_ROOT / "scripts", {".py", ".sh", ".md", ".json"}, 80),
    ("Daily Memory", REPO_ROOT / "memory", {".md"}, 120),
    ("Governance", WORKSPACE_ROOT / "governance", {".md", ".json", ".yaml", ".yml"}, 120),
    ("Workspace Docs", WORKSPACE_ROOT / "docs", {".md", ".json", ".yaml", ".yml"}, 160),
    ("Policy", WORKSPACE_ROOT / "policy", {".json", ".md", ".yaml", ".yml"}, 80),
    ("Project Docs", REPO_ROOT / "docs", {".md", ".json", ".yaml", ".yml"}, 160),
    ("Systemd", WORKSPACE_ROOT / "systemd", {".service", ".timer", ".md"}, 80),
)
ORACLE_PROJECT_SKIP_PARTS = {
    "__pycache__",
    ".backup",
    "artifacts",
    "audit",
    "node_modules",
    "runtime",
    "state",
}
ORACLE_CACHE_TTL_SECONDS = 60.0
_CACHE: dict[str, Any] = {"expires_at": 0.0, "entries": []}


def _read_json(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to parse JSON %s", path)
        return None


def _read_jsonl_rows(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        logger.exception("Failed to read JSONL rows from %s", path)
        return []
    if limit is not None and limit > 0:
        lines = lines[-limit:]
    rows: list[dict[str, Any]] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _normalize_authors(*values: Any) -> list[str]:
    labels = " ".join(str(value or "").strip().lower() for value in values if str(value or "").strip())
    rows: list[str] = []
    for key, aliases in (
        ("dali", ("dali", "jeebsdalibot")),
        ("c_lawd", ("c_lawd", "c-lawd")),
        ("lumen", ("lumen",)),
        ("chatgpt", ("chatgpt",)),
        ("grok", ("grok",)),
        ("gemini", ("gemini",)),
        ("claude code", ("claude code",)),
        ("claude (ext)", ("claude (ext)", "claude ext")),
        ("jeebs", ("jeebs", "j33bs", "jeeebs")),
    ):
        if any(alias in labels for alias in aliases):
            rows.append(key)
    return rows


def _query_tokens(question: str) -> list[str]:
    date_tokens = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", question.lower())
    raw_tokens = [token for token in re.findall(r"[a-z0-9_']+", question.lower()) if len(token) >= 3]
    stop_tokens = {
        "about",
        "agent",
        "agents",
        "being",
        "into",
        "just",
        "open",
        "questions",
        "source",
        "system",
        "systems",
        "well",
        "with",
        "your",
    }
    filtered = [token for token in raw_tokens if token not in stop_tokens]
    token_rows = date_tokens + (filtered or raw_tokens)
    return list(dict.fromkeys(token_rows))


def _query_intents(question: str, tokens: list[str]) -> dict[str, bool]:
    lower = str(question or "").lower()
    token_set = set(tokens)
    file_terms = {"file", "files", "path", "paths", "directory", "directories", "folder", "folders", "repo", "project"}
    plan_terms = {"plan", "plans", "implemented", "implementation", "handoff", "handoffs"}
    memory_terms = {"memory", "memories", "recall", "journal", "notes", "note"}
    research_terms = {"research", "paper", "papers", "study", "studies", "evidence"}
    return {
        "file_like": bool(token_set & file_terms) or any(term in lower for term in ("file ", "path ", "directory ", "folder ")),
        "directory_like": bool(token_set & {"directory", "directories", "folder", "folders"}),
        "plan_like": bool(token_set & plan_terms),
        "memory_like": bool(token_set & memory_terms),
        "research_like": bool(token_set & research_terms),
    }


def _excerpt(text: str, tokens: list[str], *, max_chars: int = 320) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= max_chars:
        return normalized
    lowered = normalized.lower()
    start = 0
    for token in tokens:
        idx = lowered.find(token)
        if idx >= 0:
            start = max(0, idx - max_chars // 4)
            break
    snippet = normalized[start : start + max_chars]
    if start > 0:
        snippet = "…" + snippet.lstrip()
    if start + max_chars < len(normalized):
        snippet = snippet.rstrip() + "…"
    return snippet


def _file_preview(path: Path, *, max_lines: int = 16, max_chars: int = 900) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return ""
    selected: list[str] = []
    total = 0
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#!"):
            continue
        selected.append(stripped)
        total += len(stripped)
        if len(selected) >= max_lines or total >= max_chars:
            break
    return "\n".join(selected)


def _collect_project_files(root: Path, allowed_suffixes: set[str], limit: int) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    rows: list[Path] = []
    for path in sorted(root.rglob("*")):
        if len(rows) >= limit:
            break
        if not path.is_file():
            continue
        if any(part in ORACLE_PROJECT_SKIP_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in allowed_suffixes:
            continue
        rows.append(path)
    return rows


def _path_label(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except Exception:
        return str(path)


def _memory_location(kind: str, row: dict[str, Any]) -> str | None:
    if kind == "telegram_memory":
        chat_id = str(row.get("chat_id") or "").strip()
        message_id = str(row.get("message_id") or "").strip()
        if chat_id and message_id:
            return f"telegram:{chat_id}:{message_id}"
    if kind in {"discord_memory", "discord_research"}:
        channel_id = str(row.get("channel_id") or "").strip()
        message_id = str(row.get("message_id") or "").strip()
        if channel_id and message_id:
            return f"discord:{channel_id}:{message_id}"
    return None


def _core_doc_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in ORACLE_CORE_DOC_PATHS:
        if not path.exists() or not path.is_file():
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            logger.exception("Failed to read Oracle core doc %s", path)
            continue
        if not body:
            continue
        entries.append(
            {
                "id": f"doc:{path.name}",
                "kind": "core_doc",
                "title": path.stem.replace("_", " "),
                "body": body,
                "authors": [],
                "created_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "source_label": f"Core Doc · {path.name}",
                "source_path": str(path),
                "location": str(path),
                "boost": 6,
            }
        )
    return entries


def _research_doc_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not ORACLE_RESEARCH_DOC_ROOT.exists() or not ORACLE_RESEARCH_DOC_ROOT.is_dir():
        return entries
    for path in sorted(ORACLE_RESEARCH_DOC_ROOT.glob("*.md")):
        if not path.is_file():
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            logger.exception("Failed to read Oracle research doc %s", path)
            continue
        if not body:
            continue
        entries.append(
            {
                "id": f"research-doc:{path.name}",
                "kind": "research_doc",
                "title": path.stem.replace("_", " "),
                "body": body,
                "authors": [],
                "created_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "source_label": f"Research Doc · {path.name}",
                "source_path": str(path),
                "location": str(path),
                "boost": 10,
            }
        )
    return entries


def _project_index_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for label, root, suffixes, limit in ORACLE_PROJECT_INDEX_ROOTS:
        paths = _collect_project_files(root, suffixes, limit)
        if not paths:
            continue
        rel_paths = [_path_label(path) for path in paths[:80]]
        entries.append(
            {
                "id": f"project-dir:{label.lower().replace(' ', '-')}",
                "kind": "project_directory",
                "title": f"{label} directory index",
                "body": "\n".join(rel_paths),
                "authors": [],
                "created_at": datetime.fromtimestamp(root.stat().st_mtime).isoformat() if root.exists() else "",
                "source_label": f"Project Directory · {label}",
                "source_path": str(root),
                "location": str(root),
                "boost": 5,
            }
        )
        for path in paths:
            preview = _file_preview(path)
            rel_path = _path_label(path)
            entries.append(
                {
                    "id": f"project-file:{rel_path}",
                    "kind": "project_file",
                    "title": rel_path,
                    "body": preview or rel_path,
                    "authors": [],
                    "created_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                    "source_label": f"Project File · {label}",
                    "source_path": str(path),
                    "location": str(path),
                    "boost": 9,
                }
            )
    return entries


def _correspondence_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    store_dir = REPO_ROOT / "workspace" / "store"
    if str(store_dir) not in sys.path:
        sys.path.insert(0, str(store_dir))
    try:
        from parser import parse_sections
    except Exception:
        parse_sections = None

    if parse_sections is None or not ORACLE_CORRESPONDENCE_PATH.exists():
        return entries
    try:
        for section in parse_sections(str(ORACLE_CORRESPONDENCE_PATH)):
            entries.append(
                {
                    "id": f"oq:{int(getattr(section, 'canonical_section_number', 0) or 0)}",
                    "kind": "correspondence",
                    "title": str(getattr(section, "title", "") or ""),
                    "body": str(getattr(section, "body", "") or ""),
                    "authors": [str(author) for author in list(getattr(section, "authors", []) or []) if str(author).strip()],
                    "created_at": str(getattr(section, "created_at", "") or ""),
                    "source_label": "Correspondence Ledger",
                    "source_path": str(ORACLE_CORRESPONDENCE_PATH),
                    "location": f"ledger:{getattr(section, 'section_number_filed', '') or getattr(section, 'canonical_section_number', '')}",
                    "canonical_section_number": int(getattr(section, "canonical_section_number", 0) or 0),
                    "section_number_filed": str(getattr(section, "section_number_filed", "") or ""),
                    "boost": 8,
                }
            )
    except Exception:
        logger.exception("Failed to parse Oracle correspondence corpus")
    return entries


def _structured_row_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path, kind, label, boost in (
        (ORACLE_GRAPH_PATH, "knowledge_graph", "Knowledge Graph", 7),
        (ORACLE_RESEARCH_IMPORT_PATH, "research_import", "Research Import", 7),
        (ORACLE_RESEARCH_PAPERS_PATH, "research_papers", "Research Papers", 10),
        (ORACLE_USER_INFERENCES_PATH, "user_inference", "User Inference", 10),
    ):
        for index, row in enumerate(_read_jsonl_rows(path), start=1):
            if kind == "user_inference" and str(row.get("status") or "").strip().lower() != "active":
                continue
            title = str(row.get("name") or row.get("title") or row.get("statement") or row.get("subject") or f"{label} {index}").strip()
            body_bits = [row.get("content"), row.get("statement"), row.get("prompt_line"), row.get("summary"), row.get("topic")]
            body = "\n".join(str(bit).strip() for bit in body_bits if str(bit or "").strip())
            if not body:
                continue
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            source_hint = (
                metadata.get("topic")
                or row.get("topic")
                or row.get("source")
                or row.get("entity_type")
                or row.get("inference_type")
                or label
            )
            entries.append(
                {
                    "id": f"{kind}:{index}",
                    "kind": kind,
                    "title": title,
                    "body": body,
                    "authors": _normalize_authors(row.get("author_name"), row.get("subject")),
                    "created_at": str(row.get("created_at") or row.get("updated_at") or row.get("distilled_at") or ""),
                    "source_label": f"{label} · {source_hint}",
                    "source_path": str(path),
                    "location": str(path),
                    "boost": boost,
                }
            )
    return entries


def _preference_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    preference_profile = _read_json(ORACLE_PREFERENCE_PROFILE_PATH)
    if not isinstance(preference_profile, dict):
        return entries
    updated_at = str(preference_profile.get("updated_at") or "")
    for section_name, section_payload in preference_profile.items():
        if section_name in {"schema_version", "subject", "updated_at"} or not isinstance(section_payload, dict):
            continue
        for key, row in section_payload.items():
            if not isinstance(row, dict) or not row.get("value"):
                continue
            title = f"{section_name.replace('_', ' ')} · {key.replace('_', ' ')}"
            body = "\n".join(
                bit
                for bit in (
                    str(row.get("statement") or "").strip(),
                    str(row.get("prompt_line") or "").strip(),
                    f"confidence {row.get('confidence')}" if row.get("confidence") is not None else "",
                )
                if bit
            )
            entries.append(
                {
                    "id": f"preference:{section_name}:{key}",
                    "kind": "preference_profile",
                    "title": title,
                    "body": body,
                    "authors": ["jeebs"],
                    "created_at": str(row.get("updated_at") or updated_at),
                    "source_label": "Preference Profile",
                    "source_path": str(ORACLE_PREFERENCE_PROFILE_PATH),
                    "location": str(ORACLE_PREFERENCE_PROFILE_PATH),
                    "boost": 12,
                }
            )
    return entries


def _memory_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for kind, path, limit in ORACLE_MEMORY_SOURCES:
        label = kind.replace("_", " ").title()
        for index, row in enumerate(_read_jsonl_rows(path, limit=limit), start=1):
            role = str(row.get("role") or "").strip().lower()
            if role not in {"assistant", "user"}:
                continue
            content = str(row.get("content") or "").strip()
            if len(content) < 24:
                continue
            entries.append(
                {
                    "id": f"{kind}:{index}",
                    "kind": kind,
                    "title": str(row.get("chat_title") or row.get("channel_name") or row.get("guild_name") or label).strip(),
                    "body": content,
                    "authors": _normalize_authors(row.get("author_name"), role),
                    "created_at": str(row.get("created_at") or row.get("stored_at") or ""),
                    "source_label": f"{label} · {role}",
                    "source_path": str(path),
                    "location": _memory_location(kind, row) or str(path),
                    "boost": 8 if kind == "discord_research" else (4 if role == "assistant" else 3),
                }
            )
    return entries


def corpus_entries(*, force: bool = False) -> list[dict[str, Any]]:
    now = time.time()
    if not force and _CACHE["expires_at"] > now:
        return list(_CACHE["entries"])

    entries = []
    entries.extend(_correspondence_entries())
    entries.extend(_structured_row_entries())
    entries.extend(_preference_entries())
    entries.extend(_memory_entries())
    entries.extend(_research_doc_entries())
    entries.extend(_core_doc_entries())
    entries.extend(_project_index_entries())
    _CACHE["entries"] = entries
    _CACHE["expires_at"] = now + ORACLE_CACHE_TTL_SECONDS
    return list(entries)


def invalidate_corpus_cache() -> None:
    _CACHE["entries"] = []
    _CACHE["expires_at"] = 0.0


def build_lexical_oracle_payload(
    question: str,
    *,
    k: int = 10,
    being: str | None = None,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    token_rows = _query_tokens(question)
    query_text = str(question or "").lower()
    being_filter = str(being or "").strip().lower()
    intents = _query_intents(question, token_rows)

    def score_entry(entry: dict[str, Any]) -> int:
        authors = " ".join(str(author).lower() for author in list(entry.get("authors") or []))
        if being_filter and being_filter not in authors:
            return 0
        title = str(entry.get("title") or "").lower()
        body = str(entry.get("body") or "").lower()
        source_label = str(entry.get("source_label") or "").lower()
        location = str(entry.get("location") or entry.get("source_path") or "").lower()
        kind = str(entry.get("kind") or "").lower()
        score = 0
        matched = False
        if query_text and query_text in title:
            score += 16
            matched = True
        if query_text and query_text in body:
            score += 10
            matched = True
        if query_text and query_text in source_label:
            score += 6
            matched = True
        for token in token_rows:
            title_hits = title.count(token)
            author_hits = authors.count(token)
            source_hits = source_label.count(token)
            body_hits = body.count(token)
            location_hits = location.count(token)
            score += title_hits * 5
            score += author_hits * 3
            score += source_hits * 2
            score += body_hits
            score += location_hits * 4
            if title_hits or author_hits or source_hits or body_hits or location_hits:
                matched = True
        if not matched:
            return 0
        if intents["file_like"]:
            if kind == "project_file":
                score += 18
            elif kind == "project_directory":
                score += 11
            elif kind == "correspondence":
                score -= 5
        if intents["directory_like"] and kind == "project_directory":
            score += 10
        if intents["plan_like"]:
            if kind in {"project_file", "project_directory"}:
                score += 8
            if "plan" in title or "plan" in body or "plan" in location:
                score += 6
        if intents["memory_like"]:
            if kind in {"telegram_memory", "discord_memory", "discord_research"}:
                score += 10
            if "/memory/" in location or title == "memory" or title.startswith("memory "):
                score += 8
        if intents["research_like"] and kind in {"research_doc", "research_papers", "research_import", "knowledge_graph"}:
            score += 10
        score += int(entry.get("boost") or 0)
        return score

    ranked: list[tuple[int, dict[str, Any]]] = []
    all_entries = corpus_entries()
    for entry in all_entries:
        score = score_entry(entry)
        if score <= 0:
            continue
        ranked.append((score, entry))
    ranked.sort(key=lambda row: (-row[0], -int(bool(row[1].get("created_at"))), str(row[1].get("title") or "")))

    selected = ranked[: max(1, int(k))]
    being_counts: dict[str, int] = {}
    known_beings = {
        "claude code",
        "c_lawd",
        "lumen",
        "dali",
        "chatgpt",
        "grok",
        "gemini",
        "claude (ext)",
        "claude ext",
        "jeebs",
        "the correspondence",
    }
    results: list[dict[str, Any]] = []
    locations: list[dict[str, str]] = []
    seen_locations: set[str] = set()
    for score, entry in selected:
        authors = [str(author) for author in list(entry.get("authors") or []) if str(author).strip()]
        for author in authors:
            normalized = author.lower()
            known_beings.add(normalized)
            being_counts[normalized] = being_counts.get(normalized, 0) + 1
        location = str(entry.get("location") or entry.get("source_path") or "")
        result_row = {
            "title": str(entry.get("title") or ""),
            "body": _excerpt(str(entry.get("body") or ""), token_rows),
            "authors": authors,
            "created_at": str(entry.get("created_at") or ""),
            "relevance_score": score,
            "source_label": str(entry.get("source_label") or "System Corpus"),
            "corpus_kind": str(entry.get("kind") or "system"),
            "corpus_path": str(entry.get("source_path") or ""),
            "canonical_section_number": int(entry.get("canonical_section_number", 0) or 0),
            "section_number_filed": str(entry.get("section_number_filed", "") or ""),
            "location": location,
        }
        results.append(result_row)
        if location and location not in seen_locations:
            locations.append(
                {
                    "kind": result_row["corpus_kind"],
                    "label": result_row["title"] or result_row["source_label"],
                    "location": location,
                }
            )
            seen_locations.add(location)

    centroid = next(iter(sorted(being_counts.items(), key=lambda item: (-item[1], item[0]))), (None, 0))[0]
    payload = {
        "question": question,
        "k": max(1, int(k)),
        "model": "system-corpus-lexical",
        "section_count": len(all_entries),
        "results": results,
        "being_counts": being_counts,
        "centroid": centroid,
        "not_in_top_k": sorted([being_name for being_name in known_beings if being_name not in being_counts]),
        "total_slots": sum(being_counts.values()),
        "source": "system_corpus",
        "locations": locations,
    }
    if being:
        payload["being_filter"] = being
    if fallback_reason:
        payload["fallback_reason"] = fallback_reason
    return payload


__all__ = [
    "ORACLE_CACHE_TTL_SECONDS",
    "ORACLE_CORE_DOC_PATHS",
    "ORACLE_CORRESPONDENCE_PATH",
    "ORACLE_GRAPH_PATH",
    "ORACLE_MEMORY_SOURCES",
    "ORACLE_PREFERENCE_PROFILE_PATH",
    "ORACLE_PROJECT_INDEX_ROOTS",
    "ORACLE_RESEARCH_DOC_ROOT",
    "ORACLE_RESEARCH_IMPORT_PATH",
    "ORACLE_RESEARCH_PAPERS_PATH",
    "ORACLE_USER_INFERENCES_PATH",
    "build_lexical_oracle_payload",
    "corpus_entries",
    "invalidate_corpus_cache",
]
