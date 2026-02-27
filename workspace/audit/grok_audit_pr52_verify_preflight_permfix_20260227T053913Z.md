# PR52 — verify_preflight permission fix
timestamp_utc: 20260227T053913Z

Symptom
- workspace/scripts/verify.sh failed with: verify_preflight.sh: Permission denied
- then regression.sh permission denied during Step 2 due direct exec + non-executable mode

Cause
- script executable bits were missing for scripts invoked by verify.sh

Fix
- chmod +x workspace/scripts/verify_preflight.sh
- chmod +x workspace/scripts/regression.sh
- chmod +x workspace/scripts/verify_llm_policy.sh
- chmod +x workspace/scripts/verify_coding_ladder.sh
- chmod +x workspace/scripts/verify_policy_router.sh
- chmod +x workspace/scripts/verify_intent_failure_scan.sh
- hardening: verify.sh preflight invocation uses bash explicitly

Verification
- bash workspace/scripts/regression.sh: exit 0
- bash workspace/scripts/verify.sh: exit 1
- Permission-denied symptoms are gone; remaining verify failures are unrelated:
  - secrets.env.template missing
  - verify_policy_router assertion failure
