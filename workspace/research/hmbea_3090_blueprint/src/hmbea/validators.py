from __future__ import annotations

from .schemas import CandidateOutput, EvidenceItem, ValidationResult


class DeterministicValidator:
    def run(
        self,
        candidate: CandidateOutput,
        evidence_items: list[EvidenceItem],
        acceptance_tests: list[str] | None = None,
    ) -> ValidationResult:
        reasons: list[str] = []
        schema_valid = bool(candidate.summary and candidate.answer)
        if not schema_valid:
            reasons.append("candidate missing required fields")

        evidence_ids = {item.source_id for item in evidence_items}
        grounded_refs = sum(1 for ref in candidate.evidence if ref in evidence_ids)
        groundedness = 0.0
        if candidate.evidence:
            groundedness = grounded_refs / len(candidate.evidence)

        # TODO: replace with real unit / integration test harness for code tasks.
        tests_passed = not acceptance_tests or schema_valid

        critic_score = min(
            1.0,
            max(
                0.0,
                (0.35 if schema_valid else 0.0)
                + (0.35 * groundedness)
                + (0.30 * candidate.confidence),
            ),
        )

        if not candidate.evidence:
            reasons.append("candidate did not cite evidence ids")
        if groundedness < 0.5:
            reasons.append("grounding below threshold")

        return ValidationResult(
            schema_valid=schema_valid,
            groundedness=groundedness,
            critic_score=critic_score,
            tests_passed=tests_passed,
            reasons=reasons,
        )
