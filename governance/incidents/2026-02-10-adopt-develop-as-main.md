INCIDENT: adopt develop history as new main base
DATE: 2026-02-10
WHY: secret purge + scanner-hardening required history rewrite; develop is clean and scanner-approved.
ACTION: rebase/reset main to develop via governed hotfix branch; merge to main via PR.
RISKS: preserves old main history only via GitHub refs; new canonical history starts at develop root.
