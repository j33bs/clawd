"""HMBEA Validators"""
from .schemas import ValidationResult, CandidateAnswer, EvidenceItem


class DeterministicValidator:
    """Deterministic validation of model outputs."""
    
    def run(self, candidate: CandidateAnswer, evidence: list[EvidenceItem], 
            acceptance_tests: list) -> ValidationResult:
        """Run validation checks."""
        reasons = []
        
        # Check schema validity (basic check)
        schema_valid = bool(candidate.answer and candidate.confidence >= 0)
        
        # Check groundedness (simplified - check if evidence IDs are referenced)
        evidence_ids_used = set(candidate.evidence_ids)
        evidence_ids_available = {e.source_id for e in evidence}
        groundedness = len(evidence_ids_used & evidence_ids_available) / max(len(evidence_ids_used), 1)
        
        # Default critic score (would integrate actual critic model)
        critic_score = candidate.confidence
        
        # Tests passed (placeholder)
        tests_passed = True
        
        return ValidationResult(
            schema_valid=schema_valid,
            groundedness=groundedness,
            critic_score=critic_score,
            tests_passed=tests_passed,
            reasons=reasons
        )
