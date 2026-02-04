# Tiered Cognitive Load Routing System

## Overview

The Tiered Cognitive Load Routing System is an advanced architecture designed to intelligently route incoming messages based on their cognitive complexity, perform intent disambiguation using local LLM classification, and implement reflexive context compaction with epistemic tagging.

## Architecture Components

### 1. Cognitive Load Tiers

The system classifies messages into four distinct cognitive load tiers:

#### Tier 1: Light Processing (`tier_1_light`)
- **Complexity Threshold**: ≤ 1.0
- **Examples**: Simple greetings, basic questions, direct commands
- **Processing Time**: ~100ms
- **Handler**: `simple_response_handler`
- **Characteristics**: Single-step processing, direct responses

#### Tier 2: Moderate Processing (`tier_2_moderate`)
- **Complexity Threshold**: 1.0 - 2.5
- **Examples**: Multi-part questions, explanations, simple analyses
- **Processing Time**: ~500ms
- **Handler**: `moderate_reasoning_handler`
- **Characteristics**: Multi-step reasoning required

#### Tier 3: Heavy Processing (`tier_3_heavy`)
- **Complexity Threshold**: 2.5 - 4.0
- **Examples**: Complex analyses, comparisons, strategic planning
- **Processing Time**: ~2000ms
- **Handler**: `complex_analysis_handler`
- **Characteristics**: Extensive reasoning, synthesis of multiple concepts

#### Tier 4: Critical Processing (`tier_4_critical`)
- **Complexity Threshold**: > 4.0
- **Examples**: Emergency situations, critical decision-making, system failures
- **Processing Time**: ~5000ms
- **Handler**: `emergency_handler`
- **Characteristics**: Highest priority, immediate attention required

### 2. Intent Classification and Disambiguation

The system performs sophisticated intent classification using both pattern matching and local LLM analysis:

#### Known Intents
- `information_request`: Requests for information
- `command`: Direct commands or instructions
- `question`: Various types of questions
- `feedback`: User feedback or opinions
- `problem_report`: Reports of issues or problems
- `request_for_help`: Explicit help requests
- `opinion`: Expression of opinions
- `statement`: Factual statements
- `clarification`: Requests for clarification
- `disambiguation`: Requests to resolve ambiguity
- `context_update`: Updates to context
- `task_completion`: Completion of tasks

#### Disambiguation Process
The system identifies potentially ambiguous messages and applies disambiguation logic to determine the most appropriate intent classification.

### 3. Reflexive Context Compaction

The system automatically manages context size while preserving important information:

#### Compaction Strategy
- **Target Size**: Configurable default of 1000 characters
- **Essential Keys**: Preserved during compaction (`current_task`, `critical_info`, etc.)
- **Compression Ratio**: Maintains between 30-80% of original size

#### Prioritization Logic
Context items are prioritized based on:
- Epistemic tag weights
- Essential key status
- Recency of information
- Relevance to current task

### 4. Epistemic Tagging

All context items are tagged with epistemic metadata indicating the nature of the knowledge:

#### Tag Types
- `certain_fact`: Verified, factual information (weight: 1.0)
- `probable_inference`: Reasonable inferences from evidence (weight: 0.8)
- `observation`: Direct observations (weight: 0.7)
- `assumption`: Working assumptions (weight: 0.5)
- `hypothetical`: Speculative content (weight: 0.3)
- `uncertain`: Low-confidence information (weight: 0.2)

## Implementation Details

### Cognitive Load Classification Algorithm

The system uses a multi-factor approach to determine cognitive load:

1. **Word Count**: Longer messages generally require more processing
2. **Question Words**: Presence of "what", "why", "how", etc. increases complexity
3. **Complexity Keywords**: Words like "analyze", "compare", "evaluate" indicate higher load
4. **Logical Connectors**: "and", "but", "because", etc. add reasoning complexity
5. **Negations**: "not", "never", etc. increase cognitive load
6. **Numerical Information**: Numbers often require additional processing

### Context Management

The system maintains routing statistics and performance metrics:

- Total messages processed
- Distribution across cognitive tiers
- Intent classification frequencies
- Performance metrics by tier

## Configuration

The system is highly configurable through the `cognitive_config.json` file, allowing adjustment of:
- Tier thresholds and processing parameters
- Intent classification settings
- Context compaction parameters
- Epistemic tagging weights
- Performance settings

## Benefits

1. **Efficient Resource Allocation**: Routes messages to appropriate processing levels
2. **Improved Response Times**: Lighter tasks are processed faster
3. **Better Context Management**: Maintains optimal context size
4. **Knowledge Transparency**: Epistemic tagging provides clarity on information reliability
5. **Scalability**: Handles varying complexity loads efficiently

## Usage Example

```python
from cognitive_load_router import MessageRouter

router = MessageRouter()

# Route a message
result = router.route_message("Analyze the economic impact of renewable energy...")

print(f"Cognitive Tier: {result['cognitive_tier']}")
print(f"Intent: {result['intent_classification']['intent']}")
print(f"Compacted Context: {result['compacted_context']}")
```

This system provides a robust foundation for intelligent message processing with adaptive complexity management.