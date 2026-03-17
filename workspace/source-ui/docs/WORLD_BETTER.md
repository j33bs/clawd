# Source World-Better Planning

This layer turns the Source mission into a three-year public-benefit planning surface.

Canonical inputs:
- `workspace/source-ui/config/source_mission.json`
- `workspace/source-ui/api/world_better.py`
- `workspace/scripts/generate_three_year_world_better_roadmap.py`

Canonical API payloads:
- `/api/portfolio` under `world_better`
- `/api/world-better`

## What changed

Each mission task can now carry:
- `impact_vector`
- `time_horizon`
- `beneficiaries`
- `public_benefit_hypothesis`
- `leading_indicators`
- `guardrails`
- `evidence_status`
- `reversibility`
- `leverage`

The world-better planner then computes:
- a public-benefit scorecard
- highest-leverage next moves
- a three-phase roadmap over 36 months
- guardrail gaps
- beneficiary coverage

## Design rule

This layer is intentionally heuristic and operator-legible.
It is not a substitute for outcome evaluation.
Its job is to make implicit mission assumptions explicit enough to review, challenge, and improve.
