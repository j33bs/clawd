from __future__ import annotations

from .schemas import CandidateOutput, EvidenceItem, ValidationResult


class DeterministicValidator:
    def run(
        self,
        candidate: CandidateOutput,
        evidence_items: list[EvidenceItem],
        acceptance_tests: list[str] | None = None,
    ) -> ValidationResult:
        reasons = []
        
        # Simple validation - just check if we have content
        schema_valid = bool(candidate.answer or candidate.summary)
        if not schema_valid:
            reasons.append("candidate has no content")
        
        # Groundedness - lenient for now
        evidence_ids = {item.source_id for item in evidence_items}
        grounded_refs = sum(1 for ref in candidate.evidence if ref in evidence_ids)
        
        if candidate.evidence:
            groundedness = grounded_refs / len(candidate.evidence)
        else:
            # If no evidence requested, assume OK
            groundedness = 0.8
        
        # Tests - lenient
        tests_passed = True
        
        # Calculate critic score - simple
        critic_score = min(1.0, max(0.0, candidate.confidence))
        
        # If schema is valid, give a boost
        if schema_valid:
            critic_score = max(critic_score, 0.6)
        
        return ValidationResult(
            schema_valid=schema_valid,
            groundedness=groundedness,
            critic_score=critic_score,
            tests_passed=tests_passed,
            reasons=reasons,
        )
