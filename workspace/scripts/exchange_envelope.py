#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ENVELOPE_DIR = REPO_ROOT / "workspace" / "exchanges" / "envelopes"

REQUIRED_FIELDS = ["from_node", "to_node", "utc", "subject", "references", "body", "checksum"]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_without_checksum(payload: dict[str, Any]) -> bytes:
    obj = dict(payload)
    obj.pop("checksum", None)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_checksum(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_without_checksum(payload)).hexdigest()


def validate_payload(payload: dict[str, Any]) -> tuple[bool, str]:
    for field in REQUIRED_FIELDS:
        if field not in payload:
            return False, f"missing field: {field}"
    if not isinstance(payload.get("references"), list):
        return False, "references must be an array"
    expected = compute_checksum(payload)
    if payload.get("checksum") != expected:
        return False, "checksum mismatch"
    return True, "ok"


def create_envelope(from_node: str, to_node: str, subject: str, body: str, references: list[str]) -> Path:
    payload = {
        "from_node": from_node,
        "to_node": to_node,
        "utc": _utc_now(),
        "subject": subject,
        "references": references,
        "body": body,
    }
    payload["checksum"] = compute_checksum(payload)
    ENVELOPE_DIR.mkdir(parents=True, exist_ok=True)
    ts = payload["utc"].replace("-", "").replace(":", "")
    out = ENVELOPE_DIR / f"{ts}_{from_node}_to_{to_node}.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def send_envelope(path: Path, to_node: str) -> dict[str, Any]:
    tailscale = shutil.which("tailscale")
    if not tailscale:
        return {
            "status": "tailscale_not_found",
            "recommended_command": f"tailscale file cp {path} {to_node}:",
        }
    proc = subprocess.run([tailscale, "file", "cp", str(path), f"{to_node}:"], capture_output=True, text=True, check=False)
    return {
        "status": "sent" if proc.returncode == 0 else "send_failed",
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create/validate/send peer exchange envelopes")
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--path")
    parser.add_argument("--from-node")
    parser.add_argument("--to-node")
    parser.add_argument("--subject", default="")
    parser.add_argument("--body", default="")
    parser.add_argument("--references", nargs="*", default=[])
    args = parser.parse_args()

    if args.create:
        if not args.from_node or not args.to_node:
            raise SystemExit("--from-node and --to-node are required for --create")
        out = create_envelope(args.from_node, args.to_node, args.subject, args.body, list(args.references))
        print(json.dumps({"status": "created", "path": str(out.relative_to(REPO_ROOT))}, sort_keys=True))
        return 0

    if args.validate:
        if not args.path:
            raise SystemExit("--path is required for --validate")
        payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
        ok, msg = validate_payload(payload)
        print(json.dumps({"status": "ok" if ok else "invalid", "message": msg}, sort_keys=True))
        return 0 if ok else 1

    if args.send:
        if not args.path or not args.to_node:
            raise SystemExit("--path and --to-node are required for --send")
        result = send_envelope(Path(args.path), args.to_node)
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("status") in {"sent", "tailscale_not_found"} else 1

    raise SystemExit("one of --create, --validate, --send is required")


if __name__ == "__main__":
    raise SystemExit(main())
