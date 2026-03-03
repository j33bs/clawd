from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .message import (
        MESSAGE_HASH_VERSION_LEGACY,
        MESSAGE_HASH_VERSION_V2,
        canonical_message_hash_v2,
        legacy_message_hash,
    )
except Exception:
    from message import (  # type: ignore
        MESSAGE_HASH_VERSION_LEGACY,
        MESSAGE_HASH_VERSION_V2,
        canonical_message_hash_v2,
        legacy_message_hash,
    )


def _load_verify_chain():
    try:
        from witness_ledger import verify_chain  # type: ignore
    except Exception:
        scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from witness_ledger import verify_chain  # type: ignore
    return verify_chain


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    session_id: str
    witnessed_events: int
    head_hash: str
    error: str = ""
    detail: str = ""


def _content_only_hash(message: dict[str, Any]) -> str:
    return hashlib.sha256(str((message or {}).get("content", "")).encode("utf-8")).hexdigest()


def _session_id_from_path(session_path: Path) -> str:
    return str(session_path.stem)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw = line.strip()
        if not raw:
            continue
        payload = json.loads(raw)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def default_ledger_path(repo_root: Path) -> Path:
    return Path(repo_root) / "workspace" / "state_runtime" / "teamchat" / "witness_ledger.jsonl"


def default_session_path(repo_root: Path) -> Path:
    sessions_dir = Path(repo_root) / "workspace" / "state_runtime" / "teamchat" / "sessions"
    candidates = [p for p in sessions_dir.glob("*.jsonl") if p.is_file()]
    if not candidates:
        raise FileNotFoundError(f"no session files found under {sessions_dir}")
    candidates.sort(key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)
    return candidates[0]


def _index_session_messages(rows: list[dict[str, Any]]) -> tuple[dict[tuple[str, int, str], dict[str, Any]], str]:
    indexed: dict[tuple[str, int, str], dict[str, Any]] = {}
    for row in rows:
        role = str(row.get("role", ""))
        if not role.startswith("agent:"):
            continue
        meta = dict(row.get("meta", {}) or {})
        session_id = str(meta.get("session_id", "")).strip()
        if not session_id:
            continue
        try:
            turn = int(meta.get("turn", 0))
        except Exception:
            continue
        key = (session_id, turn, role)
        if key in indexed:
            raise ValueError(f"duplicate session message key: {key}")
        indexed[key] = row
    return indexed, ""


def _expected_hashes(message_row: dict[str, Any], *, session_id: str, turn: int) -> dict[str, str]:
    return {
        MESSAGE_HASH_VERSION_V2: canonical_message_hash_v2(message_row, session_id=session_id, turn=turn),
        MESSAGE_HASH_VERSION_LEGACY: legacy_message_hash(message_row),
        "content-only": _content_only_hash(message_row),
    }


def verify_session_witness(session_path: Path, ledger_path: Path) -> VerificationResult:
    session_path = Path(session_path)
    ledger_path = Path(ledger_path)
    session_id = _session_id_from_path(session_path)
    if not session_path.exists():
        return VerificationResult(False, session_id, 0, "", "session_missing", str(session_path))
    if not ledger_path.exists():
        return VerificationResult(False, session_id, 0, "", "ledger_missing", str(ledger_path))

    verify_chain = _load_verify_chain()
    chain = verify_chain(str(ledger_path))
    if not bool(chain.get("ok")):
        return VerificationResult(
            False,
            session_id,
            0,
            str(chain.get("head_hash", "") or ""),
            "ledger_chain_invalid",
            json.dumps(chain, ensure_ascii=True, sort_keys=True),
        )

    try:
        session_rows = _load_jsonl(session_path)
        ledger_rows = _load_jsonl(ledger_path)
        indexed_rows, _ = _index_session_messages(session_rows)
    except Exception as exc:
        return VerificationResult(False, session_id, 0, str(chain.get("head_hash", "") or ""), "parse_error", type(exc).__name__)

    sessions_dir = session_path.parent
    events = []
    for row in ledger_rows:
        record = row.get("record", {})
        if not isinstance(record, dict):
            continue
        if record.get("event") != "teamchat_turn":
            continue
        ref_session_id = str(record.get("session_id", "")).strip()
        if not ref_session_id:
            return VerificationResult(
                False,
                session_id,
                0,
                str(chain.get("head_hash", "") or ""),
                "session_reference_missing",
                "",
            )
        if not (sessions_dir / f"{ref_session_id}.jsonl").exists():
            return VerificationResult(
                False,
                session_id,
                0,
                str(chain.get("head_hash", "") or ""),
                "referenced_session_missing",
                ref_session_id,
            )
        if str(record.get("session_id", "")).strip() != session_id:
            continue
        events.append(record)

    if not events:
        return VerificationResult(False, session_id, 0, str(chain.get("head_hash", "") or ""), "no_session_events", "")

    last_turn = 0
    for idx, record in enumerate(events, start=1):
        ref_session_id = str(record.get("session_id", "")).strip()
        if ref_session_id != session_id:
            return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "session_reference_mismatch", ref_session_id)
        try:
            turn = int(record.get("turn", 0))
        except Exception:
            return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "invalid_turn", str(record.get("turn")))
        if turn <= last_turn:
            return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "session_turn_order_invalid", f"turn={turn}")
        last_turn = turn
        agent = str(record.get("agent", "")).strip()
        key = (session_id, turn, f"agent:{agent}")
        message_row = indexed_rows.get(key)
        if not isinstance(message_row, dict):
            return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "session_message_missing", str(key))
        if str(record.get("ts", "")) != str(message_row.get("ts", "")):
            return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "timestamp_mismatch", f"turn={turn}")

        hash_version = str(record.get("message_hash_version", "")).strip()
        committed_hash = str(record.get("message_hash", "")).strip()
        expected = _expected_hashes(message_row, session_id=session_id, turn=turn)
        if hash_version == MESSAGE_HASH_VERSION_V2:
            if committed_hash != expected[MESSAGE_HASH_VERSION_V2]:
                return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "message_hash_mismatch", f"turn={turn}")
            continue
        if hash_version == MESSAGE_HASH_VERSION_LEGACY:
            if committed_hash != expected[MESSAGE_HASH_VERSION_LEGACY]:
                return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "message_hash_mismatch", f"turn={turn}")
            continue
        # Legacy compatibility: support prior entries with no explicit version.
        if committed_hash in {
            expected[MESSAGE_HASH_VERSION_LEGACY],
            expected["content-only"],
            expected[MESSAGE_HASH_VERSION_V2],
        }:
            continue
        return VerificationResult(False, session_id, idx - 1, str(chain.get("head_hash", "") or ""), "message_hash_mismatch", f"turn={turn}")

    return VerificationResult(
        True,
        session_id,
        len(events),
        str(chain.get("head_hash", "") or ""),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Team Chat witness ledger integrity for a session")
    parser.add_argument("--session", default="", help="Session id (defaults to latest session file)")
    parser.add_argument("--ledger", default="", help="Path to witness ledger JSONL")
    parser.add_argument("--repo-root", default="", help="Repository root (defaults to current working directory)")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if str(args.repo_root).strip() else Path.cwd().resolve()
    session_path = (
        Path(repo_root) / "workspace" / "state_runtime" / "teamchat" / "sessions" / f"{args.session}.jsonl"
        if str(args.session).strip()
        else default_session_path(repo_root)
    )
    ledger_path = Path(args.ledger).resolve() if str(args.ledger).strip() else default_ledger_path(repo_root)

    result = verify_session_witness(session_path, ledger_path)
    if not result.ok:
        print(
            f"FAIL session={result.session_id} witnessed_events={result.witnessed_events} "
            f"head_hash={result.head_hash or '-'} error={result.error} detail={result.detail}"
        )
        return 1
    print(
        f"PASS session={result.session_id} witnessed_events={result.witnessed_events} "
        f"head_hash={result.head_hash or '-'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
