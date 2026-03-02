# Ultra RDP Session Verification (C_LAWD -> Dali)

- Run timestamp (UTC): 2026-03-01T19:42:56Z
- Evidence directory:     ~/clawd/workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z
- Dali target: 100.113.160.1:3389
- Dali access mode for corroboration: SSH read-only
- Dali changes applied: none

## What We Verified

1. Control-plane/tailnet reachability from C_LAWD to Dali RDP port.
2. macOS client environment and RDP client app presence evidence captured.
3. Dali-side corroboration captured (OS/session env/ports/systemctl/journal) in read-only mode.
4. Evidence redaction pass completed for usernames/emails.

## What Is Not Yet Proven

- Live interactive usability proof is incomplete because Phase 1 required screenshots are missing:
  -     workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/screenshots/01_client_settings.png
  -     workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/screenshots/02_terminal_proof.png
  -     workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/screenshots/03_gui_proof.png
  -     workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/screenshots/04_clipboard_proof.png

## Evidence Files

workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/dali_journal_grd_tail.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/dali_journal_xrdp_tail.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/dali_os_release.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/dali_ports.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/dali_session_env.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/dali_systemctl_grd.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/dali_systemctl_xrdp.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/dali_uname.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/evdir_listing_after_phase2.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/evdir_listing_initial.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/mdls_tailscale_app.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/nc_dali_3389.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/operator_phase1_required.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/phase1_artifact_check.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/rdp_client_mrd_ls.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/rdp_client_windows_app_ls.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/redaction_note.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/redaction_scan_after.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/redaction_scan_before.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/sw_vers.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/system_profiler_software.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/tailscale_ip4.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/tailscale_status.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/target.txt
workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/verdict.txt

## Verdict

- Classification: **FAIL_CLIPBOARD**
- Rationale: Network and daemon evidence are healthy, but usability evidence gate (especially clipboard roundtrip + interactive screenshots) is not satisfied.

## Recommended Minimal Fix Path (No Changes Applied)

1. Complete operator Phase 1 screenshot capture into       workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z/screenshots/ with required filenames.
2. Re-run only verdict/report synthesis once screenshots are present.
3. If interactive test shows black screen/disconnect, use existing Dali journal artifacts first; then propose either:
   - GNOME RDP session lifecycle adjustment (preferred), or
   - xrdp fallback for separate-session model,
   without applying service changes until explicit approval.

## Rollback

- No configuration changes were made to Dali.
- On C_LAWD, this run created evidence artifacts only under     ~/clawd/workspace/audit/_evidence/rdp_ultra_verify_20260301T194114Z.
