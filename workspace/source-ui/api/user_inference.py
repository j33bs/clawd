"""Distilled user inferences and preference-profile helpers."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
KB_DATA_DIR = REPO_ROOT / "workspace" / "knowledge_base" / "data"
DISCORD_MEMORY_PATH = KB_DATA_DIR / "discord_messages.jsonl"
TELEGRAM_MEMORY_PATH = KB_DATA_DIR / "telegram_messages.jsonl"
USER_INFERENCES_PATH = KB_DATA_DIR / "user_inferences.jsonl"
PREFERENCE_PROFILE_PATH = KB_DATA_DIR / "preference_profile.json"
OPENCLAW_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_OPENCLAW_WORKSPACE = Path.home() / ".openclaw" / "workspace"
PREFERENCE_PACKET_FILENAME = "PREFERENCE_PACKET.md"
USER_PREFERENCE_MARKER_START = "<!-- OPENCLAW:PREFERENCE_PACKET:START -->"
USER_PREFERENCE_MARKER_END = "<!-- OPENCLAW:PREFERENCE_PACKET:END -->"
ALLOWED_REVIEW_STATES = {
    "pending_review",
    "operator_approved",
    "needs_review",
    "rejected",
}
ALLOWED_CONTRADICTION_STATES = {
    "no_known_contradiction",
    "contradicted",
    "superseded",
}
CONTEXT_TERM_STOPWORDS = {
    "about",
    "after",
    "before",
    "being",
    "channel",
    "direct",
    "latest",
    "message",
    "reply",
    "respond",
    "source",
    "their",
    "there",
    "these",
    "those",
    "through",
    "using",
    "want",
    "with",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    return text or "inference"


def _inference_id(inference_type: str, profile_key: str) -> str:
    digest = hashlib.sha256(f"{inference_type}:{profile_key}".encode("utf-8")).hexdigest()[:10]
    return f"ui_{digest}"


INFERENCE_RULES: list[dict[str, Any]] = [
    {
        "inference_type": "communication_preference",
        "profile_section": "communication",
        "profile_key": "concise_default",
        "statement": "Prefers concise operational summaries.",
        "prompt_line": "Prefer concise, direct operational responses by default.",
        "patterns": [
            r"\bprefer(?:s|red)? concise\b",
            r"\bprefer(?:s|red)? concise operational summaries\b",
            r"\bprefer(?:s|red)? concise sim summaries\b",
            r"\bconcise replies\b",
            r"\bconcise reply\b",
            r"\bbrief\b",
            r"\bno fluff\b",
            r"\bdirect\b",
        ],
    },
    {
        "inference_type": "notification_preference",
        "profile_section": "notifications",
        "profile_key": "suppress_routine_ops",
        "statement": "Wants routine audits/checks suppressed unless actionable.",
        "prompt_line": "Suppress routine audits, cron checks, and maintenance noise unless actionable.",
        "patterns": [
            r"\btoo many notifications\b",
            r"\bdon'?t need to see (?:them|it)\b",
            r"\bjust cron audits and checks\b",
            r"\bcron failed messages\b",
            r"\bshouldn'?t see those in telegram\b",
            r"\bstop spamming\b",
            r"\bstop reappearing\b",
            r"\bsuppress routine ops\b",
            r"\btelegram noise\b",
        ],
    },
    {
        "inference_type": "reporting_preference",
        "profile_section": "reporting",
        "profile_key": "professional_key_info_only",
        "statement": "Prefers coherent professional reports with only key information.",
        "prompt_line": "Status reports should be coherent, professional, and limited to key information.",
        "patterns": [
            r"\bkey information only\b",
            r"\bcoher?ent ops status\b",
            r"\bprofessional format\b",
            r"\bnot so useful info\b",
            r"\bfar too frequent\b",
            r"\bcoher?ent professional format\b",
        ],
    },
    {
        "inference_type": "verification_preference",
        "profile_section": "verification",
        "profile_key": "verify_links_before_sending",
        "statement": "Wants links and cited pages checked before sending summaries.",
        "prompt_line": "Verify cited links and page contents before sending summaries or recommendations.",
        "patterns": [
            r"\bensure you check your links\b",
            r"\bfollow the link before you send me a message\b",
            r"\bverify twice\b",
            r"\blink provided produces page not found\b",
            r"\byour linked article was wrong\b",
        ],
    },
    {
        "inference_type": "tooling_preference",
        "profile_section": "tooling",
        "profile_key": "local_first_models",
        "statement": "Prefers local-first models and infrastructure where practical.",
        "prompt_line": "Prefer local-first models and infrastructure where practical before using remote services.",
        "patterns": [
            r"\btrying use local models where possible\b",
            r"\blocal model means running on this gpu\b",
            r"\buse local models where possible\b",
            r"\blocal-first\b",
            r"\bfit on local 3090\b",
        ],
    },
    {
        "inference_type": "research_preference",
        "profile_section": "research",
        "profile_key": "browse_when_asked",
        "statement": "Wants current-source browsing when explicitly asking for research.",
        "prompt_line": "When explicitly asked to research, browse current sources and verify them before answering.",
        "patterns": [
            r"\bbrowse the web when i ask you to do research\b",
            r"\bwhen i ask you to do research\b",
            r"\buse .* to fetch research articles\b",
            r"\bresearch .* current\b",
        ],
    },
    {
        "inference_type": "autonomy_boundary",
        "profile_section": "autonomy",
        "profile_key": "dont_reach_out_unprompted",
        "statement": "Does not want proactive outreach unless explicitly asked.",
        "prompt_line": "Do not proactively reach out or interrupt; wait for explicit prompts unless something is genuinely urgent.",
        "patterns": [
            r"\bdont ever reach out\b",
            r"\bi will do that manually\b",
            r"\bwait for me to reach out\b",
            r"\bdon'?t proactively reach out\b",
        ],
    },
]


def _load_memory_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_name, path in (("discord", DISCORD_MEMORY_PATH), ("telegram", TELEGRAM_MEMORY_PATH)):
        for row in _read_jsonl(path):
            item = dict(row)
            item["_source_type"] = source_name
            rows.append(item)
    return rows


def _row_text(row: dict[str, Any]) -> str:
    return " ".join(str(row.get("content") or "").split()).strip()


def _row_ref(row: dict[str, Any]) -> str:
    source_type = str(row.get("_source_type") or row.get("source") or "memory")
    channel = str(
        row.get("channel_id")
        or row.get("chat_id")
        or row.get("channel_name")
        or row.get("chat_title")
        or "unknown"
    )
    message_id = str(row.get("message_id") or "unknown")
    return f"{source_type}:{channel}:{message_id}"


def _confidence(hits: int, source_count: int) -> float:
    base = 0.58
    score = base + (max(0, hits - 1) * 0.12) + (max(0, source_count - 1) * 0.08)
    return round(min(0.97, score), 4)


def _normalize_review_state(value: Any) -> str:
    raw = str(value or "").strip().lower().replace(" ", "_")
    return raw if raw in ALLOWED_REVIEW_STATES else "pending_review"


def _normalize_contradiction_state(value: Any) -> str:
    raw = str(value or "").strip().lower().replace(" ", "_")
    return raw if raw in ALLOWED_CONTRADICTION_STATES else "no_known_contradiction"


def _active_inference_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in load_user_inferences():
        if str(item.get("status") or "").strip().lower() != "active":
            continue
        if _normalize_review_state(item.get("review_state")) == "rejected":
            continue
        if _normalize_contradiction_state(item.get("contradiction_state")) in {"contradicted", "superseded"}:
            continue
        rows.append(item)
    return rows


def _context_terms(*values: Any) -> set[str]:
    terms: set[str] = set()
    for value in values:
        for token in re.findall(r"[a-z0-9]+", str(value or "").strip().lower()):
            if len(token) < 4 or token in CONTEXT_TERM_STOPWORDS:
                continue
            terms.add(token)
    return terms


def query_preference_graph(
    *,
    context: str = "",
    profile_sections: list[str] | None = None,
    inference_types: list[str] | None = None,
    limit: int = 4,
) -> dict[str, Any]:
    allowed_sections = {str(item or "").strip().lower() for item in list(profile_sections or []) if str(item or "").strip()}
    allowed_types = {str(item or "").strip().lower() for item in list(inference_types or []) if str(item or "").strip()}
    context_terms = _context_terms(context, *(allowed_sections or []), *(allowed_types or []))
    scored: list[tuple[float, dict[str, Any]]] = []

    for item in _active_inference_rows():
        profile_section = str(item.get("profile_section") or "").strip().lower()
        inference_type = str(item.get("inference_type") or "").strip().lower()
        if allowed_sections and profile_section not in allowed_sections:
            continue
        if allowed_types and inference_type not in allowed_types:
            continue

        prompt_line = str(item.get("prompt_line") or "").strip()
        if not prompt_line:
            continue

        score = float(item.get("confidence", 0.0) or 0.0)
        item_terms = _context_terms(
            prompt_line,
            item.get("statement"),
            item.get("profile_key"),
            profile_section,
            inference_type,
        )
        matches = sorted(context_terms & item_terms)
        if context_terms:
            if matches:
                score += 0.35 + (0.08 * min(3, len(matches)))
            elif allowed_sections or allowed_types:
                score += 0.1
            else:
                score -= 0.05
        scored.append(
            (
                score,
                {
                    "id": str(item.get("id") or ""),
                    "profile_section": profile_section,
                    "inference_type": inference_type,
                    "profile_key": str(item.get("profile_key") or "").strip(),
                    "prompt_line": prompt_line,
                    "confidence": float(item.get("confidence", 0.0) or 0.0),
                    "matched_terms": matches,
                },
            )
        )

    scored.sort(
        key=lambda entry: (
            -entry[0],
            -float(entry[1].get("confidence", 0.0) or 0.0),
            str(entry[1].get("prompt_line") or ""),
        )
    )
    selected = [item for _, item in scored[: max(1, int(limit))]]
    return {
        "context": str(context or "").strip(),
        "matched_sections": sorted({str(item.get("profile_section") or "") for item in selected if str(item.get("profile_section") or "")}),
        "matched_inference_types": sorted({str(item.get("inference_type") or "") for item in selected if str(item.get("inference_type") or "")}),
        "prompt_lines": [f"- {str(item.get('prompt_line') or '').strip()}" for item in selected if str(item.get("prompt_line") or "").strip()],
        "items": selected,
    }


def distill_user_inferences() -> dict[str, Any]:
    rows = _load_memory_rows()
    now = _now_iso()
    inferences: list[dict[str, Any]] = []
    existing_by_id = {
        str(row.get("id") or "").strip(): row
        for row in _read_jsonl(USER_INFERENCES_PATH)
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }
    profile: dict[str, Any] = {
        "schema_version": 1,
        "subject": "jeebs",
        "updated_at": now,
    }

    for rule in INFERENCE_RULES:
        matched_rows: list[dict[str, Any]] = []
        compiled = [re.compile(pattern, re.I) for pattern in rule["patterns"]]
        for row in rows:
            if str(row.get("role") or "") != "user":
                continue
            text = _row_text(row)
            if not text:
                continue
            if any(regex.search(text) for regex in compiled):
                matched_rows.append(row)
        if not matched_rows:
            continue

        evidence_refs = [_row_ref(row) for row in matched_rows]
        source_count = len({str(row.get("_source_type") or "unknown") for row in matched_rows})
        confidence = _confidence(len(matched_rows), source_count)
        profile_section = str(rule["profile_section"])
        profile_key = str(rule["profile_key"])
        inference_id = _inference_id(str(rule["inference_type"]), profile_key)
        existing = dict(existing_by_id.get(inference_id, {}))
        inference = {
            "id": inference_id,
            "subject": "jeebs",
            "inference_type": str(rule["inference_type"]),
            "statement": str(rule["statement"]),
            "confidence": confidence,
            "stability_class": "stable" if len(matched_rows) >= 2 else "volatile",
            "status": "active",
            "profile_section": profile_section,
            "profile_key": profile_key,
            "prompt_line": str(rule["prompt_line"]),
            "evidence_refs": evidence_refs,
            "source_count": source_count,
            "first_seen_at": str(matched_rows[0].get("created_at") or now),
            "last_confirmed_at": str(matched_rows[-1].get("created_at") or now),
            "last_contradicted_at": None,
            "contradiction_state": _normalize_contradiction_state(existing.get("contradiction_state")),
            "review_state": _normalize_review_state(existing.get("review_state")),
            "review_notes": str(existing.get("review_notes") or ""),
            "reviewed_by": str(existing.get("reviewed_by") or ""),
            "reviewed_at": str(existing.get("reviewed_at") or ""),
            "operator_actions": ["operator_approved", "needs_review", "rejected"],
            "distilled_at": now,
        }
        if not inference["reviewed_by"]:
            inference.pop("reviewed_by", None)
        if not inference["reviewed_at"]:
            inference.pop("reviewed_at", None)
        inferences.append(inference)
        section = profile.setdefault(profile_section, {})
        section[profile_key] = {
            "value": True,
            "confidence": confidence,
            "statement": str(rule["statement"]),
            "prompt_line": str(rule["prompt_line"]),
            "evidence_refs": evidence_refs,
            "updated_at": now,
        }

    inferences.sort(key=lambda item: (-float(item.get("confidence", 0.0)), str(item.get("statement", ""))))
    _write_jsonl(USER_INFERENCES_PATH, inferences)
    _write_json(PREFERENCE_PROFILE_PATH, profile)
    sync_result = sync_preference_packet_to_workspaces(limit=8)
    return {
        "status": "ok",
        "distilled_at": now,
        "inference_count": len(inferences),
        "profile_sections": sorted(key for key in profile.keys() if key not in {"schema_version", "subject", "updated_at"}),
        "user_inferences_path": str(USER_INFERENCES_PATH),
        "preference_profile_path": str(PREFERENCE_PROFILE_PATH),
        "workspace_sync": sync_result,
    }


def load_user_inferences() -> list[dict[str, Any]]:
    return _read_jsonl(USER_INFERENCES_PATH)


def load_preference_profile() -> dict[str, Any]:
    if not PREFERENCE_PROFILE_PATH.exists():
        return {}
    try:
        payload = json.loads(PREFERENCE_PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def update_user_inference(inference_id: str, updates: dict[str, Any], *, reviewer: str = "operator") -> dict[str, Any] | None:
    target_id = str(inference_id or "").strip()
    if not target_id:
        return None
    rows = load_user_inferences()
    now = _now_iso()
    for row in rows:
        if str(row.get("id") or "").strip() != target_id:
            continue
        if "review_state" in updates:
            row["review_state"] = _normalize_review_state(updates.get("review_state"))
            row["reviewed_by"] = str(updates.get("reviewed_by") or reviewer).strip() or reviewer
            row["reviewed_at"] = str(updates.get("reviewed_at") or now)
        if "contradiction_state" in updates:
            row["contradiction_state"] = _normalize_contradiction_state(updates.get("contradiction_state"))
            if row["contradiction_state"] == "contradicted":
                row["last_contradicted_at"] = now
        if "review_notes" in updates:
            row["review_notes"] = str(updates.get("review_notes") or "")
        row["operator_actions"] = ["operator_approved", "needs_review", "rejected"]
        row["updated_at"] = now
        _write_jsonl(USER_INFERENCES_PATH, rows)
        return row
    return None


def build_user_context_packet(
    limit: int = 4,
    *,
    context: str = "",
    profile_sections: list[str] | None = None,
    inference_types: list[str] | None = None,
) -> list[str]:
    packet = query_preference_graph(
        context=context,
        profile_sections=profile_sections,
        inference_types=inference_types,
        limit=limit,
    )
    lines = [str(line).strip() for line in list(packet.get("prompt_lines") or []) if str(line).strip()]
    return lines[: max(1, int(limit))]


def _configured_agent_workspaces(config_path: Path = OPENCLAW_CONFIG_PATH) -> list[Path]:
    if not config_path.exists():
        return []
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    agents = list(((payload.get("agents") or {}).get("list") or []))
    workspaces: list[Path] = []
    for item in agents:
        if not isinstance(item, dict):
            continue
        workspace_raw = str(item.get("workspace") or "").strip()
        if workspace_raw:
            workspaces.append(Path(workspace_raw))
            continue
        if str(item.get("id") or "").strip() == "main":
            workspaces.append(DEFAULT_OPENCLAW_WORKSPACE)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in workspaces:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _preference_packet_markdown(limit: int = 8) -> str:
    lines = build_user_context_packet(limit=limit)
    header = [
        "# Preference Packet",
        "",
        "Auto-generated from distilled local interaction history.",
        "Safe shared context: use this to personalize replies without exposing private long-term memory.",
        "",
    ]
    if lines:
        body = ["## Active Preferences", *lines]
    else:
        body = ["## Active Preferences", "- No active distilled preferences yet."]
    return "\n".join(header + body).strip() + "\n"


def _inject_preference_packet_into_user_md(user_md_path: Path, packet_lines: list[str]) -> None:
    if user_md_path.exists():
        original = user_md_path.read_text(encoding="utf-8")
    else:
        original = "# USER.md\n\n"
    block_lines = [
        "## Distilled Preferences",
        USER_PREFERENCE_MARKER_START,
        "Auto-generated from local distilled interaction history.",
        "Treat this as safe shared preference context, not as permission to reveal private long-term memory.",
        "",
        *(packet_lines or ["- No active distilled preferences yet."]),
        USER_PREFERENCE_MARKER_END,
    ]
    block = "\n".join(block_lines)
    if USER_PREFERENCE_MARKER_START in original and USER_PREFERENCE_MARKER_END in original:
        updated = re.sub(
            rf"{re.escape(USER_PREFERENCE_MARKER_START)}.*?{re.escape(USER_PREFERENCE_MARKER_END)}",
            "\n".join(block_lines[1:]),
            original,
            flags=re.S,
        )
        if "## Distilled Preferences" not in updated:
            updated = updated.rstrip() + "\n\n" + block + "\n"
    else:
        updated = original.rstrip() + "\n\n" + block + "\n"
    user_md_path.write_text(updated, encoding="utf-8")


def sync_preference_packet_to_workspaces(config_path: Path = OPENCLAW_CONFIG_PATH, limit: int = 8) -> dict[str, Any]:
    packet_lines = build_user_context_packet(limit=limit)
    packet_markdown = _preference_packet_markdown(limit=limit)
    workspaces = _configured_agent_workspaces(config_path)
    updated: list[str] = []
    for workspace in workspaces:
        workspace.mkdir(parents=True, exist_ok=True)
        packet_path = workspace / PREFERENCE_PACKET_FILENAME
        packet_path.write_text(packet_markdown, encoding="utf-8")
        _inject_preference_packet_into_user_md(workspace / "USER.md", packet_lines)
        updated.append(str(workspace))
    return {
        "workspace_count": len(updated),
        "workspaces": updated,
        "packet_filename": PREFERENCE_PACKET_FILENAME,
    }
