# INV-003 / Store Governance Threat Model

## 1. Scope
This document covers governance integrity risks for the CorrespondenceStore and INV-004 commit-gate workflow.
It does not cover general web hardening or network infrastructure; tailnet ACL design is a separate workstream.

## 2. Assets at Risk
- `workspace/governance/OPEN_QUESTIONS.md`: append-only source of truth and governance record.
- `workspace/store/lancedb_data/`: derived vector index; high rebuild cost and drift sensitivity.
- `workspace/tools/commit_gate.py`: gate semantics and PASS/FAIL authority boundary.
- `workspace/audit/`: evidence chain; tampering here breaks provenance claims.
- `workspace/governance/.section_count`: canonical section counter used for filing alignment.

## 3. Threat Actors
- External caller impersonating a being and filing malicious sections.
- Tag injection actor attempting to force `[EXEC:GOV]`-like authority claims.
- Semantic pollution actor submitting content designed to shift centroids/nearest-cluster behavior.
- Gate replay actor reusing historical PASS payloads to claim fresh approval.
- Ghosting actor inserting unsigned governance writes that evade human review.

## 4. Defenses In Place
- Sanitizer path (`workspace/store/sanitizer.py`) strips governance tag tokens from embedding inputs.
- Collision evidence (`section_number_filed` vs `canonical_section_number`) logs mismatch without silent overwrite.
- Commit gate isolation attestation requires `isolation_verified` and `isolation_evidence`.
- Joint PASS marker (`[JOINT: c_lawd + Dali]`) blocks malformed PASS claims.
- Append-only governance workflow preserves tamper-evident git history.
- `retro_dark_fields` explicitly marks missing fields instead of silently dropping uncertainty.

## 5. Defenses Not Yet In Place
- Network auth is incomplete for non-local exposure; unauthorized callers remain possible.
- Cryptographic section signing is absent; attribution is conventional, not cryptographic.
- API rate limiting is absent; flooding can distort retrieval and cost profiles.
- `[EXEC:HUMAN_OK]` policy is documented but not universally enforced mechanically.
- Audit integrity chain (hash-chained append log) is not yet implemented.

## 6. Deployment Gates (checkbox list)
- [ ] Tailnet ACL (or equivalent network auth) restricts API access to approved node identities.
- [ ] Section signing strategy chosen and validated for governance-critical writes.
- [ ] Rate limits and abuse thresholds enforced for write/query paths.
- [ ] `[EXEC:HUMAN_OK]` enforcement implemented for operations requiring human authority.
- [ ] Audit hash-chain or equivalent immutability control deployed.
- [ ] INV-003 confound controls (RULE-STORE-006) all operational before interpretive claims.
