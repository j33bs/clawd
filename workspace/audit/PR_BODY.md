### Summary
Implements capability-based model routing with explicit user triggers and subagent local default.

### Behavior
- Default conversation -> minimax-portal/MiniMax-M2.5
- Explicit triggers:
  - "use chatgpt" -> gpt-5.2-chat-latest
  - "use codex" -> gpt-5.3-codex
- Subagents -> vllm/local-assistant
- Complexity escalation:
  - planning/reasoning -> gpt-5.2-chat-latest
  - code gen -> gpt-5.3-codex
  - small code tasks -> gpt-5.3-codex-spark
- Non-escalation guard: ordinary chat ("Tell me something interesting about whales.") must remain on MiniMax default.

### Files changed
- workspace/policy/llm_policy.json
- workspace/scripts/policy_router.py
- workspace/scripts/verify_policy_router.sh (includes "no creep" guard)
- workspace/scripts/verify_coding_ladder.sh
- Audit/evidence under workspace/audit/

### Verification
Primary PR gates:
- bash workspace/scripts/verify_llm_policy.sh
- bash workspace/scripts/verify_policy_router.sh
- bash workspace/scripts/verify_coding_ladder.sh

Audit trail: workspace/audit/model_routing_20260218T194145Z.md
Baseline artifact: workspace/audit/npm_test_origin_main_20260219.txt
