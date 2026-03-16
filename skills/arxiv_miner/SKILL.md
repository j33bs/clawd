# Extracted Skill: arxiv_skill_miner

## Formal Structure
S = (C, π, T, R)

## Applicability Conditions (C)
- User requests analysis of arxiv paper for skill extraction
- Need to extract procedural knowledge from code repositories
- Goal: augment LLM with domain-specific capabilities without retraining

## Policy (π)
1. Fetch paper source via arxiv.org/e-print/{id}
2. Extract repository structure (dir hierarchy + file contents)
3. Semantic skill identification via dense retrieval:
   - Bi-encoder: encode task descriptions and code modules
   - Compute cosine similarity for candidate selection
   - Cross-encoder: refine relevance scores
4. Translate to SKILL.md format with progressive disclosure

## Triggers (T) - Termination Criteria
- Output validation: SKILL.md generated with valid S=(C,π,T,R)
- Relevance threshold τ exceeded for extracted skills
- Three-level progressive disclosure structure complete

## Interface (R)
- Input: arxiv ID (e.g., 2603.11808)
- Output: SKILL.md artifact
- Dependencies: curl, tar, tex parser

## Progressive Disclosure Architecture
- **Level 1** (30-100 tokens): Metadata YAML (Name, Description, Version, Triggers) — pre-loaded at startup
- **Level 2** (500-2000 tokens): Procedural instructions — injected on skill activation
- **Level 3**: Resources (scripts, reference docs) — loaded on-demand

## References
- arxiv:2603.11808 — Automating Skill Acquisition through Large-Scale Mining
- SKILL.md spec: Anthropic → Microsoft/lmkit open standard
