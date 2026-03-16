# Recommended model stack for a single 3090

## Conservative baseline

- **Generalist / controller**: quantized 14B dense model
- **Retrieval**: 0.6B embedding + 0.6B reranker
- **Critic**: tiny reasoning model or reuse the controller in short-context critique mode

This configuration is the best starting point if you want stable implementation rather than benchmark chasing.

## Practical specialist extension

- keep the controller resident
- load a **code-specialist** only for SWE tasks
- keep retrieval and validators always available
- do not run many medium/large models concurrently on the same GPU

## Experimental track

- test a hybrid / MoE coder only after the baseline passes evals
- reduce context aggressively during deployment experiments
- treat every experimental model as opt-in behind a registry flag

## Context policy

Do not design around 128K–256K context on a 3090 for normal agent loops.
Use:

- 8K to 16K hot working context
- retrieval compression / summarization
- sparse replay of earlier checkpoints
- file-level sharding for code tasks
