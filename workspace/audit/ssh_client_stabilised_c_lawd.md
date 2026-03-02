# SSH Client Stabilisation (C_LAWD -> Dali)

- Evidence directory:   /Users/heathyeager/clawd/workspace/audit/_evidence/ssh_client_20260228T182300Z
- Sterile test result: pass
- Alias test result: pass

## Rollback

1. Remove the appended managed block from `/Users/heathyeager/.ssh/config`:
   - from `# >>> dali-tailnet managed block (2026-02-28T18:00:00Z)`
   - through `# <<< dali-tailnet managed block`
2. Delete `/Users/heathyeager/clawd/scripts/ssh_dali.sh` if undesired.
