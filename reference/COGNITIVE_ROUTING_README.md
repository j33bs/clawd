# Tiered Cognitive Load Routing Implementation

## Overview

This implementation provides a comprehensive system for tiered cognitive-load routing with local LLM classification and intent disambiguation, plus reflexive context compaction with epistemic tagging. The system intelligently routes messages based on their cognitive complexity, manages context efficiently, and provides transparency about knowledge sources and confidence levels.

## Files Included

### 1. `cognitive_load_router.py`
Core implementation containing:
- `MessageRouter` class for handling the routing logic
- `IntentClassifier` for intent detection and disambiguation
- `ContextCompactor` for managing context size
- `EpistemicTagger` for knowledge confidence tagging
- `CognitiveLoadTier` and `EpistemicTag` enums

### 2. `cognitive_config.json`
Configuration file defining:
- Tier thresholds and processing parameters
- Intent classification settings
- Context compaction parameters
- Epistemic tagging weights
- Performance settings

### 3. `test_cognitive_router.py`
Comprehensive test suite demonstrating:
- Basic message routing functionality
- Context compaction capabilities
- Intent disambiguation
- System statistics collection

### 4. `COGNITIVE_ROUTING_DOCS.md`
Detailed documentation covering:
- Architecture overview
- Component descriptions
- Implementation details
- Usage examples

## Features

### Tiered Cognitive Load Routing
- Four-tier system (Light, Moderate, Heavy, Critical)
- Automatic classification based on message complexity
- Configurable thresholds and processing handlers

### Intent Classification & Disambiguation
- Pattern matching for quick classification
- Local LLM integration for complex cases
- Disambiguation for ambiguous messages
- Confidence scoring for classifications

### Reflexive Context Compaction
- Automatic context size management
- Preservation of essential information
- Configurable compression ratios
- Intelligent prioritization based on importance

### Epistemic Tagging
- Knowledge confidence indicators
- Source attribution for information
- Weighted importance scoring
- Transparency about knowledge certainty

## Usage

### Basic Usage
```python
from cognitive_load_router import MessageRouter

# Initialize the router
router = MessageRouter()

# Route a message
result = router.route_message("Your message here", context=context_data)

# Access routing results
print(f"Cognitive Tier: {result['cognitive_tier']}")
print(f"Intent: {result['intent_classification']['intent']}")
print(f"Compacted Context: {result['compacted_context']}")
```

### Advanced Configuration
Adjust settings in `cognitive_config.json` to customize:
- Processing thresholds
- Context size limits
- Tag weights
- Performance parameters

### Running Tests
Execute the test suite to verify functionality:
```bash
python test_cognitive_router.py
```

## Benefits

1. **Resource Optimization**: Efficient allocation of processing resources based on message complexity
2. **Response Time Improvement**: Faster processing for simpler tasks
3. **Context Management**: Maintains optimal context size without losing important information
4. **Knowledge Transparency**: Clear indication of information reliability through epistemic tagging
5. **Scalability**: Handles varying complexity loads effectively
6. **Adaptability**: Highly configurable for different use cases

## Integration

This system can be integrated into:
- Chatbot frameworks
- AI assistants
- Customer service systems
- Content analysis platforms
- Decision support systems

## Next Steps

For full deployment, consider:
- Integration with your preferred local LLM
- Performance tuning based on your specific requirements
- Monitoring and logging setup
- Security considerations for sensitive contexts

The system provides a solid foundation for intelligent message processing with adaptive complexity management and transparent knowledge handling.