# Benchmark plan

## Domains

- code editing / repository navigation
- structured reasoning / planning
- retrieval-grounded synthesis
- tool invocation with typed outputs
- safety / refusal / approval handling

## Core metrics

- task success rate
- schema-valid output rate
- escalation rate
- retry rate
- unit / integration test pass rate
- retrieval hit quality
- p50 and p95 latency
- GPU memory headroom
- tokens per successful task

## Acceptance gates

### Controller promotion

- >= 90% schema-valid rate
- >= 80% task success on low/medium difficulty
- <= 15% unnecessary escalation on low difficulty

### Code specialist promotion

- >= 70% repository-task success on your local benchmark
- >= 85% patch applicability
- >= 90% syntax-valid output

### Graph release gate

- no critical security regression
- no approval bypass
- no secret leakage in traces
- no degradation on frozen benchmark set beyond threshold
