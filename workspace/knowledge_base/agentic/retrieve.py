"""
Multi-Step Retrieval
Coordinates ModernBERT/LanceDB retrieval with optional HiveMind and graph overlays.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from .intent import build_search_query, extract_entities_from_query

from retrieval import retrieve as vector_retrieve


def run_hivemind_query(query: str, agent: str = "main", limit: int = 5) -> List[Dict]:
    """Run HiveMind query."""
    try:
        result = subprocess.run(
            [
                "python3",
                "scripts/memory_tool.py",
                "query",
                "--agent",
                agent,
                "--q",
                query,
                "--limit",
                str(limit),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(Path(__file__).parents[2].parent.parent),
        )

        if result.returncode != 0:
            return []

        data = json.loads(result.stdout)

        results = []
        for row in data.get("results", []):
            results.append(
                {
                    "source": "hivemind",
                    "type": row.get("kind", "fact"),
                    "scope": row.get("agent_scope", "shared"),
                    "content": row.get("content", "")[:500],
                    "metadata": row.get("metadata", {}),
                }
            )
        return results
    except Exception as exc:  # pragma: no cover
        return [{"source": "hivemind", "error": str(exc)}]


def run_graph_search(
    query: str,
    limit: int = 5,
    overlay_doc_ids: list[str] | None = None,
    overlay_paths: list[str] | None = None,
) -> List[Dict]:
    """Search knowledge graph and attach vector-retrieval overlay context."""
    try:
        result = subprocess.run(
            ["python3", "workspace/knowledge_base/kb.py", "graph", "--limit", str(limit)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(Path(__file__).parents[2].parent.parent),
        )

        if result.returncode != 0:
            return []

        overlay_doc_ids = overlay_doc_ids or []
        overlay_paths = overlay_paths or []
        overlay_lines = []
        if overlay_doc_ids:
            overlay_lines.append(f"overlay_doc_ids={', '.join(overlay_doc_ids[:8])}")
        if overlay_paths:
            overlay_lines.append(f"overlay_paths={', '.join(overlay_paths[:8])}")

        content = result.stdout[:500]
        if overlay_lines:
            content = f"{content}\n{'; '.join(overlay_lines)}"

        return [
            {
                "source": "graph",
                "type": "entity",
                "content": content,
                "query": query,
                "overlay_doc_ids": overlay_doc_ids,
                "overlay_paths": overlay_paths,
            }
        ]
    except Exception as exc:  # pragma: no cover
        return [{"source": "graph", "error": str(exc)}]


def _resolve_retrieval_mode(query: str, intent: Dict[str, Any]) -> str:
    strategy = str(intent.get("strategy", "")).lower()
    if strategy in {"governance", "research", "code_critical"}:
        return "PRECISE"
    if strategy in {"search_autocomplete", "search_only"}:
        return "FAST"

    query_lower = query.lower()
    if any(token in query_lower for token in ["governance", "research", "code-critical"]):
        return "PRECISE"
    return "HYBRID"


def _vector_context_to_result(context: Dict[str, Any], mode: str, authoritative: bool) -> Dict[str, Any]:
    return {
        "source": "kb_vectors",
        "type": "document",
        "title": context.get("path", ""),
        "path": context.get("path", ""),
        "doc_id": context.get("doc_id", ""),
        "chunk_id": context.get("chunk_id", ""),
        "score": context.get("score", 0.0) or 0.0,
        "content": context.get("text", "")[:1200],
        "retrieval_mode": mode,
        "authoritative": authoritative,
        "model_id": context.get("model_id", ""),
    }


def multi_step_retrieve(query: str, intent: Dict, agent: str = "main") -> Dict:
    """
    Execute multi-step retrieval based on intent.

    Returns:
        {
            "qmd": [...],  # now backed by KB vectors
            "hivemind": [...],
            "graph": [...],
            "combined": [...]
        }
    """
    search_query = build_search_query(query)
    entities = extract_entities_from_query(query)
    mode = _resolve_retrieval_mode(query, intent)

    vector = vector_retrieve(query, mode=mode, k=12)
    contexts = vector.get("contexts", [])

    qmd_results = [
        _vector_context_to_result(ctx, mode=vector.get("mode", mode), authoritative=bool(vector.get("authoritative")))
        for ctx in contexts
    ]

    results = {
        "query": query,
        "intent": intent,
        "entities": entities,
        "vector": vector,
        "qmd": qmd_results,
        "hivemind": [],
        "graph": [],
        "combined": [],
    }

    steps = intent.get("steps", ["hivemind_query", "graph_search"])

    overlay_doc_ids = [str(row.get("doc_id", "")) for row in contexts if row.get("doc_id")]
    overlay_paths = [str(row.get("path", "")) for row in contexts if row.get("path")]
    seen_doc_ids: set[str] = set()
    dedup_doc_ids = []
    for doc_id in overlay_doc_ids:
        if doc_id in seen_doc_ids:
            continue
        seen_doc_ids.add(doc_id)
        dedup_doc_ids.append(doc_id)

    seen_paths: set[str] = set()
    dedup_paths = []
    for path in overlay_paths:
        if path in seen_paths:
            continue
        seen_paths.add(path)
        dedup_paths.append(path)

    if "hivemind_query" in steps:
        results["hivemind"] = run_hivemind_query(search_query, agent, limit=5)

    if "graph_search" in steps or dedup_doc_ids or dedup_paths:
        results["graph"] = run_graph_search(
            query=search_query,
            limit=5,
            overlay_doc_ids=dedup_doc_ids,
            overlay_paths=dedup_paths,
        )

    combined = []

    for row in results["qmd"]:
        row["priority"] = 1
        combined.append(row)

    for row in results["hivemind"]:
        row["priority"] = 2
        combined.append(row)

    for row in results["graph"]:
        row["priority"] = 3
        combined.append(row)

    combined.sort(key=lambda item: (item.get("priority", 99), -(float(item.get("score", 0.0) or 0.0))))
    results["combined"] = combined

    return results
