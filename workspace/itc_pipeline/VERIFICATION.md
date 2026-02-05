# ITC Pipeline Telegram Ingestion - Verification Procedures

## Prerequisites

1. **Python 3.8+** installed
2. **Telethon** library installed
3. **Telegram API credentials** from https://my.telegram.org/apps
4. **Access to target ITC chats** (must be a member)

---

## Setup Commands

### 1. Install Dependencies

```bash
pip install telethon
```

### 2. Set Environment Variables

Create or update `secrets.env`:

```bash
# Required - get from https://my.telegram.org/apps
export TG_API_ID="your_api_id"
export TG_API_HASH="your_api_hash"
export TG_PHONE="+1234567890"  # Your phone with country code

# Optional - will use defaults otherwise
export TG_SESSION_PATH="C:/Users/heath/.openclaw/.secrets/telethon_itc.session"
```

On Windows (PowerShell):
```powershell
$env:TG_API_ID = "your_api_id"
$env:TG_API_HASH = "your_api_hash"
$env:TG_PHONE = "+1234567890"
```

### 3. Authenticate Telethon Session

```bash
cd C:/Users/heath/.openclaw/workspace
python -m itc_pipeline.telegram_reader_telethon --auth
```

This will:
1. Prompt for phone verification code
2. Create session file at `.secrets/telethon_itc.session`
3. Display your user ID

**Save the session file securely - it grants access to your Telegram account.**

---

## Chat ID Discovery

### 4. List All Dialogs

```bash
cd C:/Users/heath/.openclaw/workspace
python scripts/itc/telegram_list_dialogs.py
```

**Expected output:**
```
================================================================
Telegram Dialog Listing
================================================================
Session: C:/Users/heath/.openclaw/.secrets/telethon_itc.session

Logged in as: YourName (@yourusername) [ID: 123456789]

TYPE         CHAT_ID              TITLE                                    USERNAME
--------------------------------------------------------------------------------------------
Supergroup   -1001234567890       ITC Lifetime Lounge                      @itc_lounge
Supergroup   -1009876543210       Into the Cryptoverse Chat (Private)
...
--------------------------------------------------------------------------------------------
Total: XX dialogs

Output written to: C:/Users/heath/.openclaw/tmp/telegram_dialogs.tsv

================================================================
TARGET CHATS FOUND (from specification):
================================================================
  chat_id=-1001234567890       ITC Lifetime Lounge
  chat_id=-1009876543210       Into the Cryptoverse Chat (Private)
  ...

Recommended ALLOWED_CHAT_IDS:
  export ALLOWED_CHAT_IDS="-1001234567890,-1009876543210,..."
================================================================
```

### 5. Set Allowlist

Copy the recommended `ALLOWED_CHAT_IDS` from the output above:

```bash
export ALLOWED_CHAT_IDS="-1001234567890,-1009876543210,-1001122334455"
```

Or add to `secrets.env`:
```
ALLOWED_CHAT_IDS=-1001234567890,-1009876543210,-1001122334455
```

---

## Verification Tests

### Test 1: Verify Allowlist Loading

```bash
cd C:/Users/heath/.openclaw/workspace
python -c "from itc_pipeline.allowlist import log_allowlist_on_startup; import logging; logging.basicConfig(level=logging.INFO); log_allowlist_on_startup()"
```

**Expected output:**
```
============================================================
ITC Pipeline - Allowlist Configuration
============================================================
Allowed chat IDs: 3 entries
  - -1001234567890
  - -1009876543210
  - -1001122334455
Excluded patterns: {'responder', 'mbresponder', 'mresponder', 'botfather'}
============================================================
```

### Test 2: Dry-Run Ingestion

Start the ingestion in dry-run mode (logs but doesn't process):

```bash
cd C:/Users/heath/.openclaw/workspace
python -m itc_pipeline.telegram_reader_telethon --run --dry-run -v
```

**Expected output:**
```
2026-02-05 12:00:00 [INFO] itc_pipeline.allowlist: ============================================================
2026-02-05 12:00:00 [INFO] itc_pipeline.allowlist: ITC Pipeline - Allowlist Configuration
2026-02-05 12:00:00 [INFO] itc_pipeline.allowlist: ============================================================
2026-02-05 12:00:00 [INFO] itc_pipeline.allowlist: Allowed chat IDs: 3 entries
...
2026-02-05 12:00:00 [INFO] itc_pipeline.telegram_reader_telethon: Connected as: YourName (@username) [ID: 123456789]

================================================================
Telethon Ingestion Running
================================================================
Mode: DRY-RUN
Monitoring 3 allowed chats
Press Ctrl+C to stop
================================================================
```

Now send a test message to one of the allowed chats. You should see:

```
2026-02-05 12:01:00 [INFO] itc_pipeline.allowlist: ACCEPT: chat_id=-1001234567890 title='ITC Lifetime Lounge' passed allowlist gate
2026-02-05 12:01:00 [INFO] itc_pipeline.ingestion_boundary: INGEST: source=telegram chat_id=-1001234567890 msg_id=12345 chat='ITC Lifetime Lounge' text_len=42
2026-02-05 12:01:00 [INFO] itc_pipeline.ingestion_boundary: DRY-RUN: Would process message telegram:-1001234567890:12345
```

### Test 3: Verify Non-Allowed Chat Drops

Send a message to a chat NOT in the allowlist. You should see (with `-v` flag):

```
2026-02-05 12:02:00 [DEBUG] itc_pipeline.allowlist: DROP: chat_id=-1005555555555 title='Some Other Chat' not in allowlist (3 entries)
```

### Test 4: Live Ingestion

Run without dry-run to actually process messages:

```bash
cd C:/Users/heath/.openclaw/workspace
python -m itc_pipeline.telegram_reader_telethon --run -v
```

Check the output queue:
```bash
cat C:/Users/heath/.openclaw/telegram/itc_incoming_queue.jsonl
```

**Expected format:**
```json
{"source": "telegram", "chat_id": -1001234567890, "message_id": 12345, "date": "2026-02-05T12:00:00+00:00", "sender_id": 987654321, "sender_name": "User Name (@username)", "chat_title": "ITC Lifetime Lounge", "text": "Hello world", "raw_metadata": {...}, "classification": null, "authority_weight": null}
```

---

## Rollback Procedure

If issues occur:

```bash
# Stop the ingestion process (Ctrl+C)

# Remove new code
rm -rf C:/Users/heath/.openclaw/workspace/itc_pipeline
rm -rf C:/Users/heath/.openclaw/workspace/scripts/itc

# Remove runtime files
rm -f C:/Users/heath/.openclaw/telegram/itc_*.json
rm -f C:/Users/heath/.openclaw/telegram/itc_*.jsonl
rm -rf C:/Users/heath/.openclaw/tmp/telegram_dialogs.tsv

# Optionally remove session (will require re-auth)
rm -rf C:/Users/heath/.openclaw/.secrets/
```

Or revert the git commit:
```bash
git revert <commit-hash>
```

---

## Troubleshooting

### "TG_API_ID environment variable not set"
Set the environment variable or add to secrets.env and source it.

### "ABORT: Allowlist is empty"
Run `telegram_list_dialogs.py` first to discover chat IDs, then set `ALLOWED_CHAT_IDS`.

### "Session file not found" / Authentication prompts
Run `--auth` first to create the session file.

### Messages not appearing
- Verify you're a member of the target chats
- Check the allowlist includes the correct numeric chat_id (not username)
- Enable `-v` for debug logging to see drops

### Rate limiting
Telethon handles basic rate limiting automatically. For very high volume, consider adding delays.

---

## Verification Checklist

- [ ] Dependencies installed (`pip install telethon`)
- [ ] Environment variables set (TG_API_ID, TG_API_HASH, TG_PHONE)
- [ ] Authentication completed (`--auth`)
- [ ] Dialog listing works (`telegram_list_dialogs.py`)
- [ ] Allowlist configured (`ALLOWED_CHAT_IDS`)
- [ ] Dry-run shows ACCEPT for allowed chats
- [ ] Dry-run shows DROP for non-allowed chats
- [ ] Live mode produces output in `itc_incoming_queue.jsonl`
- [ ] Dedupe prevents duplicate processing
