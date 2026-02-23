# MAEBE: Multi-Agent Emergent Behavior Evaluation Framework

**Source:** arXiv:2506.03053 (June 2025, revised July 2025)
**Authors:** Sinem Erisken et al.

**Added:** 2026-02-24

## Key Innovation

**Multi-Agent Emergent Behavior Evaluation (MAEBE) framework** — systematically assess risks from multi-agent systems:

> "Traditional AI safety evaluations focusing on isolated LLMs are insufficient for prevalent multi-agent AI ensembles, which introduce novel emergent risks."

## Risks Identified

1. **Miscoordination** — agents pulling in different directions
2. **Conflict** — agents working against each other
3. **Confusion** — unclear who is responsible
4. **LLM-to-LLM prompt injection** — agents can influence each other

## The Framework

- Scalable and benchmark-agnostic
- Compares safety/alignment of isolated LLMs vs multi-agent systems
- Designed for emergent risks that only appear in ensembles

## Relevance to TACTI

Our governance framework addresses exactly these risks:
- **Miscoordination** — our routing protocols
- **Conflict** — structured friction protocol
- **Confusion** — origin tags, clear attribution
- **Prompt injection** — exec_tags isolation

This is the **safety complement** to our collective intelligence ambition.

## Connection to Emergent Coordination Paper

The Riedl paper (we added earlier) showed how to MEASURE emergence.
MAEBE shows how to EVALUATE safety of emergence.
Together: measure + evaluate = complete framework.

## Quote

> "As increasing levels of independence and agency are granted to AI, achieving safety and alignment of agent ensembles becomes critical."

## Reference
- arXiv:2506.03053
