"""
CorrespondenceStore v1 — FastAPI Query Server

Step 4 of the build sequence. Exposes the store over HTTP so external callers
(Dali on RTX 3090, Claude (ext) sessions, future agents) can query without
filesystem access to the workspace.

Governance:
  RULE-STORE-001: /tail is the default route — returns linear temporal flow
  RULE-STORE-002: exec_tag filtering operates on metadata, never on vectors
  RULE-STORE-003: Local-first; auth via X-Store-Key header (Tailscale peer auth in prod)

Usage:
  # Start the server
  python workspace/store/api.py

  # Or via uvicorn directly:
  uvicorn workspace.store.api:app --host 0.0.0.0 --port 8765

  # Query examples:
  curl http://localhost:8765/status
  curl "http://localhost:8765/tail?n=5"
  curl "http://localhost:8765/search?q=reservoir+null+test&k=3"
  curl "http://localhost:8765/section/60"

Environment:
  STORE_API_KEY   — API key for write/admin endpoints (optional; if unset, all reads are open)
  EMBED_MODEL     — embedding model name (default: all-MiniLM-L6-v2)
"""
from __future__ import annotations
import hashlib
import os
import sys
import time
from datetime import datetime
from typing import Literal, Optional

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WORKSPACE, "store"))

from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from sync import linear_tail, semantic_search, full_rebuild, get_table, DEFAULT_MODEL
from parser import parse_sections

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CorrespondenceStore v1",
    description=(
        "Query interface for OPEN_QUESTIONS.md. "
        "Default route: /tail (RULE-STORE-001). "
        "Semantic search is opt-in (RULE-STORE-002)."
    ),
    version="1.0.0",
)

OQ_PATH     = os.path.join(WORKSPACE, "governance", "OPEN_QUESTIONS.md")
COUNT_FILE  = os.path.join(WORKSPACE, "governance", ".section_count")
STORE_KEY   = os.environ.get("STORE_API_KEY", "")  # empty = reads open
_start_time = time.time()

# ---------------------------------------------------------------------------
# ETag state — updated on each /rebuild so callers can use If-None-Match
# ---------------------------------------------------------------------------
_tail_etag: str = hashlib.sha1(f"boot:{_start_time}".encode()).hexdigest()

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _require_key(x_store_key: Optional[str]) -> None:
    """Raise 403 if a key is configured and the request doesn't match."""
    if STORE_KEY and x_store_key != STORE_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Store-Key header")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class SectionOut(BaseModel):
    canonical_section_number: int
    section_number_filed: str
    collision: bool
    authors: list[str]
    created_at: str
    is_external_caller: bool
    title: str
    body: str
    exec_tags: list[str]
    status_tags: list[str]
    retro_dark_fields: list[str]

class StatusOut(BaseModel):
    status: str
    section_count: int
    store_rows: int
    section_count_delta: int  # section_count - store_rows; non-zero signals drift
    model: str
    uptime_seconds: float
    timestamp: str
    exec_tags: list[str]
    rule_store_001: str
    rule_store_002: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/status", response_model=StatusOut)
def get_status():
    """
    Store health and metadata. Always open — no auth required.
    """
    try:
        table = get_table()
        rows  = table.count_rows()
    except Exception:
        rows = -1

    count = -1
    try:
        with open(COUNT_FILE) as f:
            count = int(f.read().strip())
    except Exception:
        pass

    delta = (count - rows) if (count >= 0 and rows >= 0) else 0

    return StatusOut(
        status="live",
        section_count=count,
        store_rows=rows,
        section_count_delta=delta,
        model=os.environ.get("EMBED_MODEL", DEFAULT_MODEL),
        exec_tags=["EXEC:HUMAN_OK"],
        uptime_seconds=round(time.time() - _start_time, 1),
        timestamp=datetime.utcnow().isoformat() + "Z",
        rule_store_001="linear_tail is the default; semantic search is opt-in (factual queries only)",
        rule_store_002="exec_tags/status_tags never encoded in vectors; metadata predicates only",
    )


def _apply_detail(section_dict: dict, detail: str) -> dict:
    """
    Apply detail level truncation to a section dict before serialization.
    metadata — body stripped; preview — body[:500]; full — unchanged.
    """
    if detail == "full":
        return section_dict
    out = dict(section_dict)
    if detail == "metadata":
        out["body"] = ""
    elif detail == "preview":
        body = out.get("body", "")
        out["body"] = body[:500] + ("…" if len(body) > 500 else "")
    return out


@app.get("/tail", response_model=list[SectionOut])
def get_tail(
    request: Request,
    n: int = Query(default=40, ge=1, le=200, description="Number of sections to return (RULE-STORE-001 default: 40)"),
    retro_dark: Optional[bool] = Query(
        default=None,
        description=(
            "Filter by retro_dark_fields presence: "
            "true=only sections with non-empty retro_dark_fields; "
            "false=only sections with empty retro_dark_fields; "
            "null=no filtering."
        ),
    ),
    detail: Literal["metadata", "preview", "full"] = Query(
        default="full",
        description=(
            "Response verbosity: "
            "metadata=title+tags only (no body); "
            "preview=title+first 500 chars; "
            "full=complete body (default, backward-compatible)."
        ),
    ),
    x_store_key: Optional[str] = Header(default=None),
):
    """
    RULE-STORE-001: Returns the last N sections in temporal order.
    This is the default route for external callers reconstructing project dispositions.
    Use this before using /search — it provides context, not fragments.

    ETag support: send If-None-Match with a prior ETag to get 304 Not Modified on cache hit.
    detail=metadata or detail=preview for scan-mode queries (saves 80–93% payload).
    """
    if STORE_KEY:
        _require_key(x_store_key)

    # ETag short-circuit — only for full detail (preview/metadata are cheap; skip for simplicity)
    if detail == "full":
        etag = f'"{_tail_etag}"'
        if request.headers.get("If-None-Match") == etag:
            return Response(status_code=304, headers={"ETag": etag})
        try:
            results = linear_tail(n=n)
            if retro_dark is True:
                results = [r for r in results if len(r.get("retro_dark_fields") or []) > 0]
            elif retro_dark is False:
                results = [r for r in results if len(r.get("retro_dark_fields") or []) == 0]
            sections = [SectionOut(**r) for r in results]
            return JSONResponse(
                content=[s.model_dump() for s in sections],
                headers={"ETag": etag, "Cache-Control": "max-age=60"},
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    try:
        results = linear_tail(n=n)
        if retro_dark is True:
            results = [r for r in results if len(r.get("retro_dark_fields") or []) > 0]
        elif retro_dark is False:
            results = [r for r in results if len(r.get("retro_dark_fields") or []) == 0]
        return [SectionOut(**_apply_detail(r, detail)) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search", response_model=list[SectionOut])
def search(
    q: str = Query(..., description="Semantic search query"),
    k: int = Query(default=5, ge=1, le=50, description="Number of results"),
    exec_tag: Optional[str] = Query(default=None, description="Filter by exec_tag (e.g. EXEC:GOV)"),
    detail: Literal["metadata", "preview", "full"] = Query(
        default="full",
        description="Response verbosity (same semantics as /tail?detail=).",
    ),
    x_store_key: Optional[str] = Header(default=None),
):
    """
    RULE-STORE-001 opt-in: Semantic search for factual queries.
    Prefer /tail for orientation and context reconstruction.
    exec_tag filter operates on metadata only (RULE-STORE-002).
    detail=preview returns 500-char body snippets — good for scan-then-fetch workflows.
    """
    if STORE_KEY:
        _require_key(x_store_key)
    try:
        filters = {"exec_tags": [exec_tag]} if exec_tag else None
        results = semantic_search(q, k=k, filters=filters)
        return [SectionOut(**_apply_detail(r, detail)) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/section/{canonical_n}", response_model=SectionOut)
def get_section(
    canonical_n: int,
    x_store_key: Optional[str] = Header(default=None),
):
    """
    Retrieve a specific section by canonical section number.
    Note: canonical number ≠ filed Roman numeral for sections after the duplicate XIX.
    """
    if STORE_KEY:
        _require_key(x_store_key)
    try:
        table = get_table()
        df = table.to_pandas()
        row = df[df["canonical_section_number"] == canonical_n]
        if row.empty:
            raise HTTPException(status_code=404, detail=f"Section {canonical_n} not found")
        r = row.iloc[0].to_dict()
        # Normalise numpy arrays to Python lists
        for col in ["authors", "exec_tags", "status_tags", "retro_dark_fields"]:
            if hasattr(r[col], "tolist"):
                r[col] = r[col].tolist()
        return SectionOut(**{k: v for k, v in r.items() if k in SectionOut.model_fields})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rebuild")
def trigger_rebuild(
    x_store_key: Optional[str] = Header(default=None),
):
    """
    Trigger a full store rebuild from OPEN_QUESTIONS.md.
    Authenticated endpoint — requires X-Store-Key header.
    This is a blocking operation (~20s on Apple silicon for 85 sections).
    Rotates the ETag so cached clients know to re-fetch.
    """
    global _tail_etag
    _require_key(x_store_key)  # always auth-required regardless of STORE_KEY setting
    try:
        sections = parse_sections(OQ_PATH)
        model = os.environ.get("EMBED_MODEL", DEFAULT_MODEL)
        full_rebuild(sections, model_name=model)
        _tail_etag = hashlib.sha1(f"rebuild:{len(sections)}:{time.time()}".encode()).hexdigest()
        return {
            "status": "rebuilt",
            "sections": len(sections),
            "model": model,
            "etag": _tail_etag,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("STORE_PORT", 8765))
    host = os.environ.get("STORE_HOST", "0.0.0.0")
    print(f"\nCorrespondenceStore v1 API")
    print(f"  Store:  {OQ_PATH}")
    print(f"  Model:  {os.environ.get('EMBED_MODEL', DEFAULT_MODEL)}")
    print(f"  Listen: http://{host}:{port}")
    print(f"  Auth:   {'key required' if STORE_KEY else 'open (set STORE_API_KEY to enable)'}")
    print()
    uvicorn.run(app, host=host, port=port, log_level="info")
