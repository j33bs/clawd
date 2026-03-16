# Cron Store Authority

## Rule

For this workspace, the **live cron scheduler authority** is:

- `/Users/heathyeager/clawd/.openclaw/cron/jobs.json`

Do **not** assume that `~/.openclaw/cron/jobs.json` is the active store.

## Why this matters

A real failure occurred where a valid daily briefing job existed in `~/.openclaw/cron/jobs.json` but never fired, because the scheduler was actually reading the workspace-local store instead. The result was silent non-delivery despite the job appearing to exist.

## Best practice

Before diagnosing or editing cron jobs:

1. Check live scheduler status.
   - Use the cron status surface/tool and confirm `storePath`.
2. Treat that `storePath` as canonical.
3. Add/update/remove jobs only against the live store.
4. If a job exists in a different store, treat it as archival or stale unless proven active.

## Verification checklist

- Confirm `cron status` reports the expected store path.
- Confirm the target job exists in that store.
- Confirm next run time is present.
- Confirm recent runs appear in the same scheduler context.

## Operational doctrine

For automated systems with multiple possible persistence roots:

- **runtime authority beats assumed default paths**
- **observed live store beats historical location**
- **a job existing somewhere is not evidence it will fire**

## Current canonical note

As of 2026-03-17, the live scheduler store for this workspace is:

- `/Users/heathyeager/clawd/.openclaw/cron/jobs.json`
