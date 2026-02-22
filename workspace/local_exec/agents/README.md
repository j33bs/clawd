# Local Exec Specialist Agents

- Source of truth: `workspace/local_exec/agents/AGENT_PROMPTS.json`
- Purpose: governed prompt dictionary for bounded coordinator/coder/verifier/auditor/doc-compactor roles.
- All agents follow deny-by-default tool access and append-only evidence requirements.

Cross-check protocol (required):
1. `coordinator` assigns bounded jobs and budgets.
2. `coder_*` proposes patch/test actions.
3. `verifier_tests` validates deterministically.
4. `auditor_evidence` confirms evidence completeness + safety.
5. `doc_compactor` prepares concise operator summary with cited artifacts.
