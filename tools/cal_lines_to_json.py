#!/usr/bin/env python3
import sys, json

lines = sys.stdin.read().splitlines()
events = []
for ln in lines:
    parts = ln.split("\t")
    if len(parts) < 7:
        continue
    eid, title, cal, start, end, loc, notes = parts[:7]
    events.append({
        "id": eid,
        "title": title,
        "calendar": cal,
        "start": start,
        "end": end,
        "location": loc,
        "notes": notes,
    })

print(json.dumps({"ok": True, "events": events}, ensure_ascii=False))
