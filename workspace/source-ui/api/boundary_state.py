"""Shared provenance/shareability boundary helpers for Source UI surfaces."""

from __future__ import annotations

from typing import Any


_VALID_TONES = {"healthy", "warning", "error", "neutral"}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _truncate(value: str, *, limit: int = 260) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _tone(value: Any, *, fallback: str = "neutral") -> str:
    raw = _clean(value).lower()
    return raw if raw in _VALID_TONES else fallback


def boundary_item(key: str, label: str, detail: str = "", *, tone: str = "neutral") -> dict[str, str]:
    return {
        "key": _clean(key),
        "label": _clean(label),
        "detail": _truncate(detail),
        "tone": _tone(tone),
    }


def build_boundary(*items: dict[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "key": _clean(item.get("key")),
            "label": _clean(item.get("label")),
            "detail": _truncate(item.get("detail")),
            "tone": _tone(item.get("tone")),
        }
        for item in items
        if isinstance(item, dict) and _clean(item.get("label"))
    ]
    summary = " | ".join(row["label"] for row in rows)
    detail = " ".join(row["detail"] for row in rows if row["detail"])
    return {
        "summary": summary,
        "detail": _truncate(detail, limit=320),
        "items": rows,
    }


def _join_labels(values: list[str]) -> str:
    rows = [value for value in values if _clean(value)]
    if not rows:
        return "unknown"
    if len(rows) == 1:
        return rows[0]
    if len(rows) == 2:
        return f"{rows[0]} and {rows[1]}"
    return f"{', '.join(rows[:-1])}, and {rows[-1]}"


def _evidence_surfaces(evidence_refs: list[str]) -> list[str]:
    labels: list[str] = []
    for ref in evidence_refs:
        source = _clean(ref).split(":", 1)[0].lower()
        if source == "telegram" and "Telegram" not in labels:
            labels.append("Telegram")
        elif source == "discord" and "Discord" not in labels:
            labels.append("Discord")
    return labels


def build_memory_source_boundary(source_id: str, label: str, latest_row: dict[str, Any] | None = None) -> dict[str, Any]:
    row = latest_row if isinstance(latest_row, dict) else {}
    if source_id == "telegram_main":
        chat_title = _clean(row.get("chat_title") or label or "telegram-main")
        return build_boundary(
            boundary_item(
                "provenance",
                "telegram ingest",
                f"Mirrored from {chat_title} into the local knowledge-base JSONL.",
            ),
            boundary_item(
                "shareability",
                "private direct chat",
                "Raw Telegram memory stays local. Distill it into reviewed shared context before reuse on other surfaces.",
                tone="warning",
            ),
        )

    if source_id == "discord_research":
        channel_name = _clean(row.get("channel_name") or label or "discord-research")
        return build_boundary(
            boundary_item(
                "provenance",
                "discord research ingest",
                f"Mirrored from #{channel_name} into the local research/memory store.",
            ),
            boundary_item(
                "shareability",
                "review before share",
                "Research-channel rows are raw notes. Promote or distill them before sending them to other surfaces.",
                tone="warning",
            ),
        )

    channel_name = _clean(row.get("channel_name") or label or "discord")
    return build_boundary(
        boundary_item(
            "provenance",
            "discord ingest",
            f"Mirrored from #{channel_name} into the local knowledge-base JSONL.",
        ),
        boundary_item(
            "shareability",
            "raw memory only",
            "Useful for recall and distillation, but do not rebroadcast raw chat memory directly.",
            tone="warning",
        ),
    )


def build_inference_boundary(row: dict[str, Any]) -> dict[str, Any]:
    evidence_refs = [str(ref) for ref in (row.get("evidence_refs") or []) if _clean(ref)]
    evidence_surfaces = _join_labels(_evidence_surfaces(evidence_refs))
    review_state = _clean(row.get("review_state") or "pending_review").lower()
    reviewed_by = _clean(row.get("reviewed_by"))
    reviewed_at = _clean(row.get("reviewed_at"))
    if review_state == "operator_approved":
        share_label = "safe shared context"
        share_detail = "Approved preference memory can be used in shared prompt packets without exposing raw long-term memory."
        share_tone = "healthy"
        approval_label = "operator approved"
        approval_detail = (
            f"Reviewed by {reviewed_by} at {reviewed_at}."
            if reviewed_by or reviewed_at
            else "Operator review completed."
        )
        approval_tone = "healthy"
    else:
        share_label = "review before share"
        share_detail = "This is a distilled candidate memory, but it still needs operator review before broad cross-surface reuse."
        share_tone = "warning"
        approval_label = "review pending"
        approval_detail = "Evidence is visible here so the operator can judge provenance before approving it for shared use."
        approval_tone = "warning"
    return build_boundary(
        boundary_item(
            "provenance",
            f"distilled from {evidence_surfaces}",
            f"Built from {len(evidence_refs)} evidence refs: {', '.join(evidence_refs[:3]) or 'no evidence refs'}",
        ),
        boundary_item("shareability", share_label, share_detail, tone=share_tone),
        boundary_item("approval", approval_label, approval_detail, tone=approval_tone),
    )


def build_preference_packet_boundary(active_inferences: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(active_inferences)
    approved = sum(1 for row in active_inferences if _clean(row.get("review_state")).lower() == "operator_approved")
    pending = max(0, total - approved)
    if total <= 0:
        return build_boundary(
            boundary_item(
                "provenance",
                "no distilled packet",
                "No active preference inferences are available yet.",
            ),
            boundary_item(
                "shareability",
                "nothing to share",
                "A safe-shared prompt packet has not been distilled yet.",
                tone="warning",
            ),
        )
    if pending <= 0:
        return build_boundary(
            boundary_item(
                "provenance",
                "distilled preference packet",
                f"Built from {total} active inferences.",
            ),
            boundary_item(
                "shareability",
                "safe shared packet",
                "Every active line is operator-approved for cross-surface personalization.",
                tone="healthy",
            ),
            boundary_item(
                "approval",
                "fully reviewed",
                "All active preference lines have operator approval.",
                tone="healthy",
            ),
        )
    return build_boundary(
        boundary_item(
            "provenance",
            "distilled preference packet",
            f"Built from {total} active inferences.",
        ),
        boundary_item(
            "shareability",
            "mixed review state",
            "This packet is visible for inspection, but some lines are still unreviewed and should be treated as provisional.",
            tone="warning",
        ),
        boundary_item(
            "approval",
            f"{pending} pending review",
            f"{approved} approved, {pending} still waiting for operator review.",
            tone="warning",
        ),
    )


def build_research_boundary(topic_count: int) -> dict[str, Any]:
    if topic_count <= 0:
        return build_boundary(
            boundary_item("provenance", "research ingest idle", "No recent research topics were ingested."),
            boundary_item("shareability", "nothing queued", "There are no raw research topics waiting for review."),
        )
    return build_boundary(
        boundary_item(
            "provenance",
            "discord research digest",
            f"Compiled from {topic_count} recent user research rows in the local Discord research store.",
        ),
        boundary_item(
            "shareability",
            "review before share",
            "These are raw research prompts or notes, not operator-approved summaries.",
            tone="warning",
        ),
    )


def build_discord_channel_boundary(
    *,
    label: str,
    enabled: bool,
    has_webhook: bool,
    auto_post: bool,
    delivery: str,
    report_mode: str = "",
) -> dict[str, Any]:
    provenance_label = "source-ui outbound preview"
    provenance_detail = (
        f"Rendered from the local portfolio/task state as a {delivery or 'webhook'} preview"
        + (f" ({report_mode})." if _clean(report_mode) else ".")
    )
    if not enabled:
        return build_boundary(
            boundary_item("provenance", provenance_label, provenance_detail),
            boundary_item(
                "shareability",
                "disabled",
                f"{label or 'This channel'} is not armed for outbound delivery.",
            ),
        )
    if not has_webhook:
        return build_boundary(
            boundary_item("provenance", provenance_label, provenance_detail),
            boundary_item(
                "shareability",
                "preview only",
                "A preview is available locally, but no webhook is configured so nothing can leave the machine.",
                tone="warning",
            ),
            boundary_item(
                "approval",
                "no outbound path",
                "Configure a webhook before this preview can be shared externally.",
            ),
        )
    if auto_post:
        return build_boundary(
            boundary_item("provenance", provenance_label, provenance_detail),
            boundary_item(
                "shareability",
                "armed outbound",
                "Webhook delivery is configured. Review this preview because it can leave the machine on the next allowed send.",
                tone="warning",
            ),
            boundary_item(
                "approval",
                "schedule or operator send",
                "Outbound delivery happens through the approved bridge path, either on schedule or via an explicit operator action.",
                tone="warning",
            ),
        )
    return build_boundary(
        boundary_item("provenance", provenance_label, provenance_detail),
        boundary_item(
            "shareability",
            "manual send only",
            "Webhook delivery is configured, but outbound sharing remains operator-triggered.",
            tone="warning",
        ),
        boundary_item(
            "approval",
            "operator triggered",
            "This preview will not leave the machine until an operator explicitly sends it.",
            tone="healthy",
        ),
    )


def build_command_receipt_boundary(receipt: dict[str, Any]) -> dict[str, Any]:
    action = _clean(receipt.get("action") or "unknown").lower()
    requires_confirmation = bool(receipt.get("requires_confirmation"))
    status = _clean(receipt.get("status") or "queued").lower()
    if any(token in action for token in ("webhook", "discord", "bridge_post", "outbound")):
        share_label = "outbound network action"
        share_detail = "This action can deliver data off-machine if approved."
        share_tone = "warning"
    elif action in {"refresh", "health_check", "status_snapshot"}:
        share_label = "local read only"
        share_detail = "This action reads or refreshes local state and does not share data externally."
        share_tone = "neutral"
    elif action == "create_task":
        share_label = "local repo write"
        share_detail = "This action updates the local Source task store only."
        share_tone = "warning"
    else:
        share_label = "local state change"
        share_detail = "This action changes local runtime state only."
        share_tone = "warning"

    if requires_confirmation or status == "pending_approval":
        approval_label = "approval required"
        approval_detail = "Review provenance and impact here before executing the command."
        approval_tone = "warning"
    else:
        approval_label = "queued in operator lane"
        approval_detail = "This receipt originated from the local operator command deck."
        approval_tone = "neutral"

    return build_boundary(
        boundary_item(
            "provenance",
            "operator command deck",
            f"Created from the local Source operator surface for action '{action or 'unknown'}'.",
        ),
        boundary_item("shareability", share_label, share_detail, tone=share_tone),
        boundary_item("approval", approval_label, approval_detail, tone=approval_tone),
    )
