Title:
feat(evolution): proprioception + narrative distill + witness ledger (flag-gated)

Body:
- Adds three flag-gated vertical slices:
  - Proprioception (OPENCLAW_ROUTER_PROPRIOCEPTION): router self-observation sampler.
  - Narrative distill (OPENCLAW_NARRATIVE_DISTILL): optional nightly distillation runner.
  - Witness ledger (OPENCLAW_WITNESS_LEDGER): hash-chain tamper-evident ledger + tests.
- Adds flag-gated scaffolds for ideas 1,3,4,5,7,8,9 (non-invasive prototypes).

## State log determinism contract
- Tracked deterministic stub: workspace/state/tacti_cr/events.jsonl (never written at runtime)
- Runtime sink (ignored): workspace/state_runtime/tacti_cr/events.jsonl
- Override: TACTI_CR_EVENTS_PATH (tests/dev can pin fixtures)
- Regression: test_flags_off_does_not_create_tacti_runtime_events_file

Verification:
- python3 -m unittest -q
- npm test --silent

Rollback:
- git revert 9c5a5bd073e4892887d7853ccea368428525ab00
