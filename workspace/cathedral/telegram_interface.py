from __future__ import annotations

import fcntl
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from threading import Event
from typing import IO, Any, Callable

from .io_utils import atomic_write_json, load_json, utc_now_iso
from .logging_utils import JsonlLogger
from .paths import RUNTIME_LOGS, TELEGRAM_POLL_LOCK_PATH, TELEGRAM_STATE_PATH, ensure_runtime_dirs


class TelegramPollerLockError(RuntimeError):
    """Raised when another long-poller already holds the bot lock."""


class TelegramConflictError(RuntimeError):
    """Raised when Telegram reports a long-poll conflict."""


class TelegramWebhookConflictError(RuntimeError):
    """Raised when a webhook is configured and long-polling is requested."""


class TelegramAPIHTTPError(RuntimeError):
    def __init__(self, *, method: str, status_code: int, body: str):
        super().__init__(f"telegram_api_http_error method={method} status={status_code}")
        self.method = method
        self.status_code = int(status_code)
        self.body = str(body or "")


class TelegramCommandInterface:
    def __init__(
        self,
        *,
        token: str,
        allowed_chat_ids: set[str] | None = None,
        state_path: Path = TELEGRAM_STATE_PATH,
        lock_path: Path = TELEGRAM_POLL_LOCK_PATH,
        autoclear_webhook: bool = False,
        debug_drain_once: bool = False,
    ):
        ensure_runtime_dirs()
        self.token = token.strip()
        self.allowed_chat_ids = {str(item) for item in (allowed_chat_ids or set())}
        self.state_path = state_path
        self.lock_path = lock_path
        self.autoclear_webhook = bool(autoclear_webhook)
        self.debug_drain_once = bool(debug_drain_once)
        self.log = JsonlLogger(RUNTIME_LOGS / "telegram_interface.log")
        self.handlers: dict[str, Callable[[str], str]] = {}
        self._lock_handle: IO[str] | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def register_handler(self, command: str, fn: Callable[[str], str]) -> None:
        self.handlers[str(command)] = fn

    def _load_offset(self) -> int:
        state = load_json(self.state_path, {"offset": 0})
        if isinstance(state, dict) and isinstance(state.get("offset"), int):
            return int(state["offset"])
        return 0

    def _save_offset(self, offset: int) -> None:
        atomic_write_json(self.state_path, {"offset": int(offset), "updated_at": utc_now_iso()})

    def _api_url(self, method: str, **params: Any) -> str:
        qs = urllib.parse.urlencode(params)
        return f"https://api.telegram.org/bot{self.token}/{method}?{qs}"

    def _api_post_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.token}/{method}"

    def _api_get_json(self, method: str, *, request_timeout: float = 25.0, **params: Any) -> dict[str, Any]:
        url = self._api_url(method, **params)
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=request_timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise TelegramAPIHTTPError(method=method, status_code=exc.code, body=body) from exc
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return {"ok": False, "result": None, "description": "invalid_payload"}
        return payload

    def _api_post_json(self, method: str, *, timeout: float = 10.0, **params: Any) -> dict[str, Any]:
        body = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(
            self._api_post_url(method),
            data=body,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise TelegramAPIHTTPError(method=method, status_code=exc.code, body=body_text) from exc
        payload = json.loads(raw or "{}")
        if not isinstance(payload, dict):
            return {"ok": False, "result": None, "description": "invalid_payload"}
        return payload

    def _acquire_poller_lock(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise TelegramPollerLockError(
                f"another poller likely running (lock={self.lock_path})"
            ) from exc
        handle.seek(0)
        handle.truncate(0)
        handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "host": socket.gethostname(),
                    "ts": utc_now_iso(),
                },
                ensure_ascii=True,
                sort_keys=True,
            )
            + "\n"
        )
        handle.flush()
        self._lock_handle = handle

    def _release_poller_lock(self) -> None:
        handle = self._lock_handle
        self._lock_handle = None
        if handle is None:
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            handle.close()
        except OSError:
            pass

    def _webhook_url_from_payload(self, payload: dict[str, Any]) -> str:
        result = payload.get("result")
        if not isinstance(result, dict):
            return ""
        url = result.get("url")
        return str(url or "").strip()

    def _is_user_service_active(self, unit: str) -> bool:
        try:
            proc = subprocess.run(
                ["systemctl", "--user", "is-active", "--quiet", unit],
                capture_output=True,
                check=False,
                timeout=1.0,
            )
        except Exception:
            return False
        return proc.returncode == 0

    def _log_potential_competitors(self) -> None:
        active_units = []
        for unit in ("openclaw-gateway.service", "openclaw-telegram.service"):
            if self._is_user_service_active(unit):
                active_units.append(unit)
        if not active_units:
            return
        self.log.log(
            "telegram_possible_competitor",
            active_services=active_units,
            message="possible competing getUpdates poller detected",
        )

    def _ensure_webhook_ready(self) -> dict[str, Any]:
        payload = self._api_get_json("getWebhookInfo", request_timeout=10.0)
        webhook_url = self._webhook_url_from_payload(payload)
        self.log.log(
            "telegram_webhook_status",
            webhook_url_present=bool(webhook_url),
            has_custom_certificate=bool((payload.get("result") or {}).get("has_custom_certificate")),
            pending_update_count=int((payload.get("result") or {}).get("pending_update_count") or 0),
        )
        if not webhook_url:
            self.log.log("telegram_webhook_none")
            return payload
        if self.autoclear_webhook:
            clear_payload = self._api_post_json(
                "deleteWebhook",
                timeout=10.0,
                drop_pending_updates="true",
            )
            self.log.log(
                "telegram_webhook_cleared",
                ok=bool(clear_payload.get("ok")),
                description=str(clear_payload.get("description") or ""),
            )
            return clear_payload
        raise TelegramWebhookConflictError(
            "webhook configured; clear it or set DALI_FISHTANK_TELEGRAM_AUTOCLEAR_WEBHOOK=1"
        )

    def _self_test(self) -> None:
        payload = self._api_get_json("getMe", request_timeout=10.0)
        result = payload.get("result") if isinstance(payload, dict) else {}
        if not payload.get("ok") or not isinstance(result, dict):
            raise RuntimeError(f"telegram getMe failed: {payload}")
        self.log.log(
            "telegram_getme_ok",
            username=str(result.get("username") or ""),
            bot_id=str(result.get("id") or ""),
        )

    def _redact_chat_id(self, chat_id: str) -> str:
        text = str(chat_id or "")
        if not text:
            return "unknown"
        if len(text) <= 4:
            return "***" + text[-1:]
        return "***" + text[-4:]

    def _get_updates(self, offset: int) -> list[dict[str, Any]]:
        try:
            payload = self._api_get_json(
                "getUpdates",
                request_timeout=25.0,
                timeout=20,  # Telegram API long-poll timeout
                offset=offset,
                allowed_updates=json.dumps(["message"]),
            )
        except TelegramAPIHTTPError as exc:
            if exc.status_code == 409:
                raise TelegramConflictError(
                    "another getUpdates consumer is active (competing poller). "
                    f"telegram 409 conflict: {exc.body[:220]}"
                ) from exc
            raise

        if not isinstance(payload, dict):
            return []
        if not payload.get("ok"):
            description = str(payload.get("description") or "")
            if "conflict" in description.lower():
                raise TelegramConflictError(
                    "another getUpdates consumer is active (competing poller). "
                    f"telegram conflict: {description[:220]}"
                )
            return []
        rows = payload.get("result")
        if not isinstance(rows, list):
            return []
        out = []
        for row in rows:
            if isinstance(row, dict):
                out.append(row)
        return out

    def _send_message(self, chat_id: str, text: str) -> None:
        self._api_post_json("sendMessage", chat_id=chat_id, text=text[:3500], timeout=10.0)

    def _dispatch_command(self, command: str, arg: str) -> str:
        handler = self.handlers.get(command)
        if handler is None:
            return f"Unknown command: {command}"
        try:
            return str(handler(arg))
        except Exception as exc:
            self.log.log("command_error", command=command, error=str(exc))
            return f"Command failed: {command}"

    def _accept_chat(self, chat_id: str) -> bool:
        if not self.allowed_chat_ids:
            return True
        return str(chat_id) in self.allowed_chat_ids

    def _handle_update(self, row: dict[str, Any]) -> int:
        update_id = int(row.get("update_id", 0))
        message = row.get("message") if isinstance(row.get("message"), dict) else None
        if message is None:
            return update_id
        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        chat_id = str(chat.get("id", ""))
        if not chat_id or not self._accept_chat(chat_id):
            return update_id
        text = str(message.get("text") or "").strip()
        if not text.startswith("/"):
            return update_id

        parts = text.split(maxsplit=1)
        command = parts[0].strip().lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        if "@" in command:
            command = command.split("@", 1)[0]

        if command not in self.handlers:
            return update_id

        self.log.log("TG_CMD", cmd=command, chat_id=self._redact_chat_id(chat_id))
        self.log.log("command_received", chat_id=self._redact_chat_id(chat_id), command=command)
        reply = self._dispatch_command(command, arg)
        self._send_message(chat_id, reply)
        self.log.log("command_replied", chat_id=self._redact_chat_id(chat_id), command=command)
        return update_id

    def run_forever(self, stop_event: Event | None = None) -> None:
        if not self.enabled:
            self.log.log("telegram_disabled")
            return
        self.log.log(
            "telegram_startup",
            token_present=bool(self.token),
            chat_id_present=bool(self.allowed_chat_ids),
            chat_id_count=len(self.allowed_chat_ids),
            mode="long-poll",
            autoclear_webhook=self.autoclear_webhook,
            lock_path=str(self.lock_path),
            hostname=socket.gethostname(),
            debug_drain_once=self.debug_drain_once,
        )
        self._log_potential_competitors()

        try:
            self._acquire_poller_lock()
        except TelegramPollerLockError as exc:
            self.log.log("telegram_lock_conflict", error=str(exc))
            raise

        try:
            self.log.log("telegram_starting_long_poll")
            self._self_test()
            self._ensure_webhook_ready()
            offset = self._load_offset()
            if self.debug_drain_once:
                updates = self._get_updates(offset)
                self.log.log("telegram_debug_drain_result", updates_count=len(updates), offset=offset)
                for row in updates:
                    update_id = int(row.get("update_id", 0))
                    offset = max(offset, update_id + 1)
                self._save_offset(offset)
                return

            self.log.log("telegram_poll_loop_active", offset=offset)
            while True:
                if stop_event is not None and stop_event.is_set():
                    self.log.log("telegram_stop")
                    return
                try:
                    updates = self._get_updates(offset)
                    for row in updates:
                        update_id = self._handle_update(row)
                        offset = max(offset, update_id + 1)
                    self._save_offset(offset)
                except TelegramConflictError as exc:
                    self.log.log(
                        "telegram_poll_conflict",
                        error=str(exc),
                        message="another getUpdates consumer is active (competing poller).",
                    )
                    raise
                except Exception as exc:
                    self.log.log("telegram_poll_error", error=str(exc))
                    time.sleep(2.0)
                    continue
                time.sleep(0.2)
        finally:
            self._release_poller_lock()
