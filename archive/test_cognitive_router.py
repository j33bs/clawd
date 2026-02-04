"""
Test script for the Tiered Cognitive Load Routing System
"""

import json
from cognitive_load_router import MessageRouter, CognitiveLoadTier, EpistemicTag

def test_basic_routing():
    """Test basic message routing functionality"""
    print("Testing Basic Message Routing")
    print("=" * 40)
    
    router = MessageRouter()
    
    # Test messages of different complexity levels
    test_cases = [
        {
            "message": "Hello",
            "expected_tier": "tier_1_light",
            "description": "Simple greeting"
        },
        {
            "message": "What time is it?",
            "expected_tier": "tier_1_light", 
            "description": "Simple question"
        },
        {
            "message": "Can you explain how machine learning works?",
            "expected_tier": "tier_2_moderate",
            "description": "Explanation request"
        },
        {
            "message": "Compare the pros and cons of renewable energy sources including solar, wind, and hydroelectric power, analyzing their efficiency, cost-effectiveness, environmental impact, and scalability for different geographic regions.",
            "expected_tier": "tier_3_heavy",
            "description": "Complex comparison analysis"
        },
        {
            "message": "CRITICAL SYSTEM ALERT: Database connection failed, all services are down, immediate intervention required!",
            "expected_tier": "tier_4_critical",
            "description": "Emergency/critical situation"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['description']}")
        print(f"Message: '{test_case['message']}'")
        
        result = router.route_message(test_case['message'])
        
        actual_tier = result['cognitive_tier']
        expected_tier = test_case['expected_tier']
        
        print(f"Expected Tier: {expected_tier}")
        print(f"Actual Tier: {actual_tier}")
        print(f"Intent: {result['intent_classification']['intent']}")
        print(f"Confidence: {result['intent_classification']['confidence']:.2f}")
        
        if actual_tier == f"{expected_tier}":
            print("✓ PASS")
        else:
            print("✗ FAIL")
    
    print(f"\nRouting Stats: {router.routing_stats}")


def test_context_compaction():
    """Test context compaction functionality"""
    print("\n\nTesting Context Compaction")
    print("=" * 40)
    
    router = MessageRouter()
    
    # Create a large context to test compaction
    large_context = {
        "conversation_history": [
            {"speaker": "user", "text": "I'm looking for information about renewable energy"},
            {"speaker": "assistant", "text": "Renewable energy comes from natural sources that are constantly replenished"},
            {"speaker": "user", "text": "What are the main types?"}, 
            {"speaker": "assistant", "text": "The main types are solar, wind, hydroelectric, geothermal, and biomass"}
        ] * 10,  # Repeat to make it large
        "user_preferences": {
            "communication_style": "formal",
            "preferred_topics": ["technology", "environment"],
            "avoid_topics": ["politics", "controversy"]
        },
        "session_data": {
            "start_time": "2023-01-01T10:00:00Z",
            "interaction_count": 42,
            "last_topic": "renewable energy",
            "context_depth": 5
        },
        "external_knowledge": [
            {
                "facts": ["Solar panels convert sunlight to electricity", "Wind turbines harness wind power"],
                "statistics": {"solar_efficiency": 0.22, "wind_capacity_factor": 0.35},
                "sources": ["Wikipedia", "Energy.gov", "Research paper X"]
            } for _ in range(5)  # Create 5 copies to make it large
        ]
    }
    
    print(f"Original context size: {len(json.dumps(large_context))} characters")
    
    # Route with large context to trigger compaction
    result = router.route_message(
        "Summarize renewable energy types again", 
        context=large_context
    )
    
    compacted_context = result['compacted_context']
    compacted_size = len(json.dumps(compacted_context)) if compacted_context else 0
    
    print(f"Compacted context size: {compacted_size} characters")
    print(f"Compression ratio: {compacted_size / len(json.dumps(large_context)):.2f}")
    
    # Check if epistemic tags were added
    has_tags = _check_for_epistemic_tags(compacted_context)
    print(f"Epistemic tags applied: {has_tags}")


def _check_for_epistemic_tags(context, found_tags=None):
    """Recursively check if epistemic tags are present in the context"""
    if found_tags is None:
        found_tags = set()
    
    if isinstance(context, dict):
        for key, value in context.items():
            if key == 'epistemic_tag':
                found_tags.add(value)
            else:
                _check_for_epistemic_tags(value, found_tags)
    elif isinstance(context, list):
        for item in context:
            _check_for_epistemic_tags(item, found_tags)
    
    return len(found_tags) > 0


def test_intent_disambiguation():
    """Test intent disambiguation functionality"""
    print("\n\nTesting Intent Disambiguation")
    print("=" * 40)
    
    router = MessageRouter()
    
    ambiguous_messages = [
        "Set the temperature to 72 degrees",
        "What is the temperature today?",
        "Change my settings to high performance mode",
        "Tell me about the weather forecast"
    ]
    
    for i, message in enumerate(ambiguous_messages, 1):
        print(f"\nTest {i}: '{message}'")
        result = router.route_message(message)
        intent_result = result['intent_classification']
        
        print(f"  Primary intent: {intent_result['intent']}")
        print(f"  Confidence: {intent_result['confidence']:.2f}")
        print(f"  Alternative intents: {intent_result['alternative_intents']}")
        print(f"  Disambiguation applied: {intent_result['disambiguation_applied']}")


def test_system_statistics():
    """Test system statistics collection"""
    print("\n\nTesting System Statistics")
    print("=" * 40)
    
    router = MessageRouter()
    
    # Process several messages to build up stats
    messages = [
        "Hello",
        "How are you?",
        "Explain quantum computing",
        "Analyze market trends",
        "Emergency: system failure!"
    ]
    
    for msg in messages:
        router.route_message(msg)
    
    stats = router.routing_stats
    print(f"Total messages processed: {stats['total_messages']}")
    print("Messages by tier:")
    for tier, count in stats['by_tier'].items():
        print(f"  {tier}: {count}")
    
    print("Messages by intent:")
    for intent, count in stats['by_intent'].items():
        print(f"  {intent}: {count}")


if __name__ == "__main__":
    print("Running Cognitive Load Router Tests")
    print("=" * 50)
    
    test_basic_routing()
    test_context_compaction()
    test_intent_disambiguation()
    test_system_statistics()
    
    print("\n" + "=" * 50)
    print("All tests completed!")