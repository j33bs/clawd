# Worktree Dirty Snapshot (BEFORE)

timestamp_utc: 20260227T132118Z
repo_root: /home/jeebs/src/clawd
branch: main
head: 6c6a52d0d74c550b92026f0cdeed8cf81b15d2d2

## git status --porcelain=v1
 M tools/apply_tailscale_serve_dashboard.sh
?? workspace/audit/worktree_dirty_snapshot_20260227T132118Z_BEFORE.md

## git diff --stat
 tools/apply_tailscale_serve_dashboard.sh | 36 ++++++++++++++++++++++++--------
 1 file changed, 27 insertions(+), 9 deletions(-)

## git diff
diff --git a/tools/apply_tailscale_serve_dashboard.sh b/tools/apply_tailscale_serve_dashboard.sh
index d0592d5..128002b 100755
--- a/tools/apply_tailscale_serve_dashboard.sh
+++ b/tools/apply_tailscale_serve_dashboard.sh
@@ -1,17 +1,35 @@
 #!/usr/bin/env bash
 set -euo pipefail
 
-if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
-  echo "Run with sudo" >&2
+TS="/usr/bin/tailscale"
+PORT="18789"
+
+# --- Preconditions ------------------------------------------------------------
+
+if ! command -v "$TS" >/dev/null 2>&1; then
+  echo "FAIL: tailscale binary not found at $TS" >&2
   exit 1
 fi
 
-if ! command -v tailscale >/dev/null 2>&1; then
-  echo "FAIL: tailscale not installed (tailscale binary missing)" >&2
-  exit 1
+# Require privilege but allow sudo -n invocation
+if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
+  echo "INFO: escalating via sudo"
+  exec sudo -n "$0" "$@"
 fi
 
-tailscale serve reset || true
-pkill -f "tailscale serve" || true
-tailscale serve --bg 18789
-tailscale serve status
+echo "Applying tailscale serve mapping (port ${PORT})..."
+
+# --- Idempotent apply ---------------------------------------------------------
+
+# Reset existing serve config (non-fatal if absent)
+"$TS" serve reset >/dev/null 2>&1 || true
+
+# Start persistent background serve
+"$TS" serve --bg "$PORT"
+
+# --- Verification -------------------------------------------------------------
+
+echo "Serve status:"
+"$TS" serve status
+
+echo "OK: tailscale serve configured on port ${PORT}"
\ No newline at end of file
