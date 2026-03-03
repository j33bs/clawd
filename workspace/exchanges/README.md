# Peer Exchange Protocol (Tailnet-Only)

This protocol is for C_Lawd <-> Dali peer exchanges.

Transport constraints:
- Use Tailscale-only transport (tailnet identity + ACLs).
- Do not open new ports.
- Recommended transports: `tailscale file cp`, tailnet SSH + rsync/scp, or tailnet-mounted shared path.

Envelope schema (JSON):
- from_node: string
- to_node: string
- utc: ISO-8601 UTC timestamp
- subject: string
- references: array of doc paths
- body: string
- checksum: sha256 of canonical JSON payload excluding checksum field

Storage:
- Append-only envelope log in `workspace/exchanges/envelopes/`.
- Validation helper: `workspace/scripts/exchange_envelope.py --validate --path <envelope.json>`.
