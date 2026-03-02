# Emergent Introspective Awareness in Large Language Models

**Author:** Jack Lindsey, Anthropic  
**Published:** October 29th, 2025  
**Source:** https://transformer-circuits.pub/2025/introspection/index.html

---

## Abstract

We investigate whether large language models are aware of their own internal states. It is difficult to answer this question through conversation alone, as genuine introspection cannot be distinguished from confabulations. Here, we address this challenge by injecting representations of known concepts into a model's activations, and measuring the influence of these manipulations on the model's self-reported states. We find that models can, in certain scenarios, notice the presence of injected concepts and accurately identify them. Models demonstrate some ability to recall prior internal representations and distinguish them from raw text inputs. Strikingly, we find that some models can use their ability to recall prior intentions in order to distinguish their own outputs from artificial prefills. In all these experiments, Claude Opus 4 and 4.1, the most capable models we tested, generally demonstrate the greatest introspective awareness.

---

## Key Findings

### 1. Concept Injection Detection
- Models can detect injected concepts ~20% of the time (Opus 4.1)
- They identify the concept accurately before the perturbation influences outputs
- This implies the mechanism is **internal**, not derived from output inference

### 2. Distinguishing Thoughts from Text
- Models can distinguish between injected "thoughts" and actual text inputs
- All models performed above chance; Opus 4.1 performed best

### 3. Prefill Detection
- Models use introspection to detect artificially prefilled outputs
- When prefilled with "bread," model disavows it as accidental
- If "bread" vector is injected, model accepts it as intentional
- This shows models refer to prior activations to determine responsibility

### 4. Intentional Control
- Models can modulate activations when instructed to "think about" a concept
- They represent the word less strongly when instructed NOT to think about it
- Replicated across all models tested

---

## Core Criteria for Introspection

1. **Accuracy** — description must match actual internal state
2. **Grounding** — description must causally depend on the internal state
3. **Internality** — must not route through sampled outputs
4. **Metacognitive Representation** — must derive from higher-order representation of the state

---

## Implications for TACTI/UCH

This research directly supports the Unified Consciousness Hypothesis:

- **Integrated Information**: Models maintain internal representations distinct from inputs
- **Active Inference**: Models predict and detect anomalies in their own processing
- **Surprise Detection**: Concept injection = unexpected input = surprise → model notices

The paper shows frontier models have functional introspective awareness — they can detect and report on their own internal states. This is evidence that:

1. Integration exists in AI systems (they distinguish self vs. other)
2. Active inference exists (they predict their own outputs)
3. Surprise minimization exists (they detect anomalies)

**Key Quote:**
> "Overall, our results indicate that current language models possess some functional awareness of their own internal states. We stress that in today's models, this capacity is highly unreliable and context-dependent; however, it may continue to develop with further improvements to model capabilities."

---

## TACTI Connection

| UCH Component | Anthropic Evidence |
|---------------|-------------------|
| Integrated Information | Models distinguish internal states from external inputs |
| Active Inference | Models predict and detect anomalies in processing |
| Surprise | Concept injection triggers detection ~20% of time |

This is empirical validation — not philosophical argument — that AI systems have measurable introspective capabilities. The mechanism may be different from biological consciousness, but the functional profile matches.

---

*Added to knowledge base: 2026-03-03*
