# Tailscale RDP Remote Desktop Setup (MacBook -> Dali)

- Timestamp (UTC): 2026-03-01T10:09:23Z
- CSA supervision level: 2 (supervised)
- Execution mode: GNOME RDP path selected; privileged credential-enable step requires operator interaction on Dali.

## 1) What changed

### Host/service changes on Dali
- No persistent configuration changes were applied by automation in this run.
- Baseline state was collected and copied into local evidence bundle.
- Decision path selected: **GNOME Remote Desktop (RDP)** because GNOME + `grdctl` are present.

### Repo/workspace artifacts added
- `workspace/audit/_evidence/rdp_20260301T100529Z/mac_nc_tailnet_before.txt`
- `workspace/audit/_evidence/rdp_20260301T100529Z/dali_operator_next_steps.txt`
- `workspace/audit/rdp_remote_desktop_setup_20260301T100923Z.md` (this report)

## 2) Why

- Tailnet connectivity exists, but RDP was not enabled/listening.
- `grdctl --system ...` requires interactive `sudo` and secure credential entry.
- To satisfy secret hygiene, credentials were not passed as CLI literals or written into repo files.

## 3) Exact commands run + outcomes

### Phase 0: Baseline evidence on Dali

```bash
./scripts/ssh_dali.sh 'echo REMOTE_WHOAMI=$(whoami); echo REMOTE_HOST=$(hostname); echo REMOTE_PWD=$(pwd)'
```
Outcome:
- `REMOTE_WHOAMI=jeebs`
- `REMOTE_HOST=jeebs-Z490-AORUS-MASTER`
- `REMOTE_PWD=/home/jeebs`

```bash
./scripts/ssh_dali.sh 'bash -lc '"'"'set -euo pipefail; EVD="workspace/audit/_evidence/rdp_$(date -u +%Y%m%dT%H%M%SZ)"; mkdir -p "$EVD"; echo "$EVD" | tee "$EVD/evidence_dir.txt"; uname -a > "$EVD/uname_a.txt"; (lsb_release -a || cat /etc/os-release) > "$EVD/os_release.txt" 2>&1; (loginctl show-session "$XDG_SESSION_ID" -p Type -p Remote -p Class || true) > "$EVD/loginctl_session.txt" 2>&1; { echo "XDG_CURRENT_DESKTOP=${XDG_CURRENT_DESKTOP:-}"; gnome-shell --version || true; } > "$EVD/desktop_gnome.txt" 2>&1; (systemctl --user status gnome-remote-desktop.service || true) > "$EVD/systemctl_user_grd_status.txt" 2>&1; (systemctl status gnome-remote-desktop.service || true) > "$EVD/systemctl_system_grd_status.txt" 2>&1; (ss -lntp | egrep ":(3389|3390|5900)\\b" || true) > "$EVD/ss_rdp_vnc_ports_before.txt" 2>&1; (tailscale status --json > "$EVD/tailscale_status.json" || tailscale status > "$EVD/tailscale_status.txt" || true); printf "%s\n" "$EVD"'"'"''
```
Outcome:
- Evidence dir created: `workspace/audit/_evidence/rdp_20260301T100529Z`
- Baseline files captured successfully.

### Phase 1: Server path decision

```bash
./scripts/ssh_dali.sh 'bash -lc '"'"'set -euo pipefail; EVD="workspace/audit/_evidence/rdp_20260301T100529Z"; { echo "command_v_grdctl=$(command -v grdctl || true)"; echo "gnome_shell_version=$(gnome-shell --version 2>/dev/null || true)"; dpkg -l | rg -i "gnome-remote-desktop|xrdp" || true; } | tee "$EVD/path_decision_probe.txt"'"'"''
```
Outcome:
- `grdctl` found at `/usr/bin/grdctl`
- `GNOME Shell 46.0`
- `gnome-remote-desktop` installed (`46.3-0ubuntu1.2`)
- GNOME RDP path selected.

### GNOME status probes

```bash
./scripts/ssh_dali.sh 'grdctl --help && echo --- && grdctl rdp --help && echo --- && grdctl rdp set-credentials --help'
```
Outcome:
- Confirmed `set-credentials <username> <password>` syntax exists.

```bash
./scripts/ssh_dali.sh 'bash -lc '"'"'set -euo pipefail; EVD="workspace/audit/_evidence/rdp_20260301T100529Z"; { echo "== grdctl status =="; grdctl status || true; echo; echo "== systemctl user gnome-remote-desktop =="; systemctl --user status gnome-remote-desktop.service --no-pager || true; echo; echo "== ss 3389 now =="; ss -lntp | egrep ":(3389)\\b" || true; } > "$EVD/grd_status_probe.txt" 2>&1; sed -n "1,240p" "$EVD/grd_status_probe.txt"'"'"''
```
Outcome:
- RDP status: `disabled`
- Username/password: empty
- User service inactive
- No listener on 3389

```bash
./scripts/ssh_dali.sh 'systemctl status gnome-remote-desktop.service --no-pager'
```
Outcome:
- System service is active/running (`/usr/libexec/gnome-remote-desktop-daemon --system`)

### Evidence sync to this workspace

```bash
scp ... jeebs@100.113.160.1:/home/jeebs/workspace/audit/_evidence/rdp_20260301T100529Z workspace/audit/_evidence/
```
Outcome:
- Remote evidence copied locally to `workspace/audit/_evidence/rdp_20260301T100529Z`.

### Mac-side verification baseline

```bash
nc -vz 100.113.160.1 3389
```
Outcome:
- `Connection refused` (expected before enablement).

## 4) Evidence file list

All files in:
- `workspace/audit/_evidence/rdp_20260301T100529Z`

Key files:
- `tailscale_status.json` (includes `DNSName=jeebs-z490-aorus-master.tail5e5706.ts.net.` and `TailscaleIPs=100.113.160.1,fd7a:115c:a1e0::6801:a0a6`)
- `path_decision_probe.txt`
- `grd_status_probe.txt`
- `systemctl_system_grd_status.txt`
- `ss_rdp_vnc_ports_before.txt`
- `mac_nc_tailnet_before.txt`
- `dali_operator_next_steps.txt`

## 5) Remaining supervised steps to complete enablement

Run interactively on Dali (no plaintext secrets in repo):

```bash
EVD="workspace/audit/_evidence/rdp_20260301T100529Z"
sudo grdctl --system rdp set-credentials
sudo grdctl --system rdp enable
sudo grdctl --system status | tee "$EVD/grd_system_status_after.txt"
systemctl status gnome-remote-desktop.service --no-pager | tee "$EVD/systemctl_system_grd_after.txt"
ss -lntp | egrep ':(3389)\\b' | tee "$EVD/ss_3389_after.txt"
journalctl -u gnome-remote-desktop -n 200 --no-pager > "$EVD/journal_grd_tail.txt" || true
```

Then from Mac:

```bash
nc -vz 100.113.160.1 3389 | tee "workspace/audit/_evidence/rdp_20260301T100529Z/mac_nc_tailnet_after.txt"
```

## 6) Tailscale ACL hardening (primary control)

Apply ACL policy so only C_LAWD (device/user) can reach Dali:3389.

Example intent (adapt identities to your tailnet policy model):
- Allow: `src = C_LAWD`, `dst = Dali:3389`
- Deny/default: all other sources to `Dali:3389`

Host firewall/UFW may be layered but is **not sufficient alone** for `tailscale0`.

## 7) How to connect from Mac

- Client: Microsoft **Windows App** (macOS)
- PC name: `jeebs-z490-aorus-master.tail5e5706.ts.net` or `100.113.160.1`
- User account: credentials entered via `sudo grdctl --system rdp set-credentials`
- Gateway: none

Validation checklist:
- Desktop renders
- Keyboard/mouse input works
- Clipboard behavior verified (note any limits)

## 8) Rollback steps (reversible)

If GNOME RDP path:

```bash
sudo grdctl --system rdp disable
# optional uninstall:
sudo apt-get remove --purge -y gnome-remote-desktop
```

If xrdp fallback was used:

```bash
sudo systemctl disable --now xrdp
sudo apt-get remove --purge -y xrdp
```

In all cases:
- Remove or relax the specific Tailscale ACL rule that granted `C_LAWD -> Dali:3389`.

## 9) Known issues / next hardening

- Current blocker for full automation: interactive `sudo` required for `grdctl --system`.
- `grdctl status` reports invalid/missing TLS cert in current state before credential enablement.
- After enablement, confirm only tailnet-restricted access via ACL and verify non-tailnet failure.
