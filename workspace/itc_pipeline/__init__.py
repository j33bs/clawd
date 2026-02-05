# ITC Pipeline - Telegram Ingestion Module
# Category: C (Feature)
"""
ITC Pipeline Telegram ingestion via Telethon (MTProto user session).

This module provides:
- telegram_reader_telethon.py: Main Telethon-based message reader
- allowlist.py: Hard allowlist gate by chat_id
- ingestion_boundary.py: Pipeline entry point with dedupe

Environment variables required:
- TG_API_ID: Telegram API ID from https://my.telegram.org
- TG_API_HASH: Telegram API Hash
- TG_SESSION_PATH: Path to session file (default: .secrets/telethon_itc.session)
- ALLOWED_CHAT_IDS: Comma-separated list of allowed numeric chat IDs
"""

__version__ = "0.1.0"
