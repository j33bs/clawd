#!/bin/bash
# Check inbox and wake session if new messages

INBOX=$(curl -s http://localhost:8766/inbox)
COUNT=$(echo "$INBOX" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")

if [ "$COUNT" -gt 0 ]; then
    echo "📨 New message(s) from Dali - triggering session wake"
    # Could use cron wake or system event
    # For now just log it
    echo "$(date): $COUNT message(s)" >> ~/messenger_wake.log
fi
