"""
Tiered Cognitive Load Routing System with Local LLM Classification
and Intent Disambiguation, plus Reflexive Context Compaction with Epistemic Tagging
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import hashlib
import re


class CognitiveLoadTier(Enum):
    """Cognitive load tiers for routing messages based on complexity"""
    TIER_1_LIGHT = "tier_1_light"      # Simple queries, direct responses
    TIER_2_MODERATE = "tier_2_moderate"  # Multi-step reasoning required
    TIER_3_HEAVY = "tier_3_heavy"      # Complex analysis, planning, synthesis
    TIER_4_CRITICAL = "tier_4_critical"  # Emergency, critical decision making


class EpistemicTag(Enum):
    """Epistemic tags for knowledge confidence and source attribution"""
    CERTAIN_FACT = "certain_fact"           # Verified information
    PROBABLE_INFERENCE = "probable_inference"  # Reasonable inference
    HYPOTHETICAL = "hypothetical"          # Speculative content
    UNCERTAIN = "uncertain"               # Low confidence
    ASSUMPTION = "assumption"             # Working assumption
    OBSERVATION = "observation"            # Direct observation


class MessageRouter:
    """
    Main class for handling tiered cognitive load routing with local LLM classification
    """
    
    def __init__(self, local_llm_client=None):
        self.local_llm_client = local_llm_client
        self.context_compactor = ContextCompactor()
        self.intent_classifier = IntentClassifier(local_llm_client)
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Create console handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        
        # Initialize routing statistics
        self.routing_stats = {
            'total_messages': 0,
            'by_tier': {tier.value: 0 for tier in CognitiveLoadTier},
            'by_intent': {}
        }
    
    def route_message(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Route a message based on cognitive load tier and perform intent disambiguation
        """
        self.routing_stats['total_messages'] += 1
        
        # Classify the intent first
        intent_classification = self.intent_classifier.classify_intent(message)
        
        # Determine cognitive load tier
        tier = self._classify_cognitive_load(message, intent_classification)
        
        # Update stats
        self.routing_stats['by_tier'][tier.value] += 1
        intent_name = intent_classification.get('intent', 'unknown')
        self.routing_stats['by_intent'][intent_name] = self.routing_stats['by_intent'].get(intent_name, 0) + 1
        
        # Perform reflexive context compaction if needed
        compacted_context = self.context_compactor.compact_context(context) if context else None
        
        # Create routing result
        result = {
            'original_message': message,
            'cognitive_tier': tier.value,
            'intent_classification': intent_classification,
            'compacted_context': compacted_context,
            'timestamp': datetime.now().isoformat(),
            'routing_id': self._generate_routing_id(message, tier.value)
        }
        
        self.logger.info(f"Routed message to {tier.value} tier with intent: {intent_classification.get('intent')}")
        
        return result
    
    def _classify_cognitive_load(self, message: str, intent_classification: Dict[str, Any]) -> CognitiveLoadTier:
        """
        Classify the cognitive load of a message using local LLM
        """
        # Define heuristics for cognitive load
        complexity_indicators = {
            'word_count': len(message.split()),
            'question_words': len(re.findall(r'\b(what|why|how|when|where|who)\b', message.lower())),
            'complexity_keywords': len(re.findall(r'\b(analyze|compare|evaluate|synthesize|plan|strategy|solution|recommendation)\b', message.lower())),
            'conjunctions': len(re.findall(r'\b(and|but|or|because|therefore|however|although)\b', message.lower())),
            'negations': len(re.findall(r'\b(not|no|never|nothing|nowhere|neither|nor|cannot)\b', message.lower())),
            'numbers': len(re.findall(r'\d+', message)),
        }
        
        # Calculate complexity score
        complexity_score = (
            min(complexity_indicators['word_count'] / 50, 2.0) +  # Max 2 points for word count
            min(complexity_indicators['question_words'], 2) * 0.5 +  # Questions add complexity
            min(complexity_indicators['complexity_keywords'], 3) * 0.8 +  # Complexity keywords
            min(complexity_indicators['conjunctions'], 5) * 0.3 +  # Logical connections
            min(complexity_indicators['negations'], 3) * 0.4 +  # Negations add complexity
            min(complexity_indicators['numbers'], 5) * 0.2  # Numbers add complexity
        )
        
        # Determine tier based on complexity score
        if complexity_score <= 1.0:
            return CognitiveLoadTier.TIER_1_LIGHT
        elif complexity_score <= 2.5:
            return CognitiveLoadTier.TIER_2_MODERATE
        elif complexity_score <= 4.0:
            return CognitiveLoadTier.TIER_3_HEAVY
        else:
            return CognitiveLoadTier.TIER_4_CRITICAL
    
    def _generate_routing_id(self, message: str, tier: str) -> str:
        """Generate a unique ID for the routing"""
        content = f"{message}_{tier}_{datetime.now().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]


class IntentClassifier:
    """
    Class for intent classification using local LLM
    """
    
    def __init__(self, local_llm_client=None):
        self.local_llm_client = local_llm_client
        self.known_intents = [
            "information_request", "command", "question", "feedback",
            "problem_report", "request_for_help", "opinion", "statement",
            "clarification", "disambiguation", "context_update", "task_completion"
        ]
    
    def classify_intent(self, message: str) -> Dict[str, Any]:
        """
        Classify the intent of a message using local LLM
        """
        # First, try pattern matching for quick classification
        intent = self._pattern_match_intent(message)
        
        if intent == "unknown":
            # Fall back to LLM classification for complex cases
            intent = self._llm_classify_intent(message)
        
        # Perform disambiguation if needed
        disambiguated_intent = self._disambiguate_intent(message, intent)
        
        return {
            'intent': disambiguated_intent,
            'confidence': 0.9 if intent != "unknown" else 0.5,
            'alternative_intents': self._find_alternative_intents(message, intent),
            'disambiguation_applied': intent != disambiguated_intent
        }
    
    def _pattern_match_intent(self, message: str) -> str:
        """
        Quick pattern matching for common intents
        """
        message_lower = message.lower().strip()
        
        # Command patterns
        if re.match(r'^(please )?(can you|could you|would you|will you) ', message_lower):
            return "request_for_help"
        
        if re.match(r'^(do|make|create|set|change|update|delete|run|execute|perform) ', message_lower):
            return "command"
        
        # Question patterns
        if re.match(r'^\s*(what|why|how|when|where|who|which|whose|whom)', message_lower):
            return "question"
        
        # Feedback patterns
        if re.search(r'\b(good|great|excellent|bad|poor|terrible|amazing|awesome|horrible|fantastic|wonderful|awful)\b', message_lower):
            return "feedback"
        
        # Problem report patterns
        if re.search(r'\b(broken|not working|error|bug|issue|problem|crash|fail|stop|break)\b', message_lower):
            return "problem_report"
        
        # Help request patterns
        if re.search(r'\b(help|assist|support|need|want|require|assist me|help me)\b', message_lower):
            return "request_for_help"
        
        # Clarification patterns
        if re.search(r'\b(what do you mean|explain|clarify|elaborate|more detail|tell me more)\b', message_lower):
            return "clarification"
        
        return "unknown"
    
    def _llm_classify_intent(self, message: str) -> str:
        """
        Use local LLM to classify intent
        """
        if not self.local_llm_client:
            return "unknown"
        
        # In a real implementation, this would call the local LLM
        # For now, we'll simulate the behavior
        return "information_request"  # Placeholder
    
    def _disambiguate_intent(self, message: str, intent: str) -> str:
        """
        Perform intent disambiguation for ambiguous cases
        """
        # Check for ambiguous terms that could indicate multiple intents
        ambiguous_patterns = [
            ("question", r"\b(what is|what are|what does|what was|what were)\b"),
            ("command", r"\b(set|configure|change|modify|adjust)\b"),
            ("information_request", r"\b(tell me|inform me|provide|give me|show me)\b")
        ]
        
        # Look for conflicting patterns
        matched_intents = []
        for possible_intent, pattern in ambiguous_patterns:
            if re.search(pattern, message.lower()) and possible_intent != intent:
                matched_intents.append(possible_intent)
        
        if len(matched_intents) > 0:
            # Return the most likely intent based on context
            return self._resolve_ambiguous_intent(message, [intent] + matched_intents)
        
        return intent
    
    def _resolve_ambiguous_intent(self, message: str, possible_intents: List[str]) -> str:
        """
        Resolve ambiguity between multiple possible intents
        """
        # Simple heuristic: return the first non-unknown intent
        for intent in possible_intents:
            if intent != "unknown":
                return intent
        return "unknown"
    
    def _find_alternative_intents(self, message: str, primary_intent: str) -> List[str]:
        """
        Find alternative intents that might apply to the message
        """
        alternatives = []
        for intent in self.known_intents:
            if intent != primary_intent and self._pattern_matches_intent(message, intent):
                alternatives.append(intent)
        return alternatives[:3]  # Return top 3 alternatives
    
    def _pattern_matches_intent(self, message: str, intent: str) -> bool:
        """
        Check if a message matches a specific intent pattern
        """
        message_lower = message.lower()
        
        if intent == "question":
            return bool(re.match(r'^\s*(what|why|how|when|where|who|which|whose|whom)', message_lower))
        elif intent == "command":
            return bool(re.match(r'^(do|make|create|set|change|update|delete|run|execute|perform) ', message_lower))
        elif intent == "feedback":
            return bool(re.search(r'\b(good|great|excellent|bad|poor|terrible|amazing|awesome|horrible|fantastic|wonderful|awful)\b', message_lower))
        elif intent == "problem_report":
            return bool(re.search(r'\b(broken|not working|error|bug|issue|problem|crash|fail|stop|break)\b', message_lower))
        elif intent == "request_for_help":
            return bool(re.search(r'\b(help|assist|support|need|want|require|assist me|help me)\b', message_lower))
        elif intent == "clarification":
            return bool(re.search(r'\b(what do you mean|explain|clarify|elaborate|more detail|tell me more)\b', message_lower))
        
        return False


class ContextCompactor:
    """
    Class for reflexive context compaction with epistemic tagging
    """
    
    def __init__(self):
        self.epistemic_tagger = EpistemicTagger()
    
    def compact_context(self, context: Dict[str, Any], target_size: int = 1000) -> Dict[str, Any]:
        """
        Compact context while preserving important information and adding epistemic tags
        """
        if not context:
            return {}
        
        # Add epistemic tags to context items
        tagged_context = self._tag_context_with_epistemology(context)
        
        # Perform compaction if needed
        compacted = self._perform_compaction(tagged_context, target_size)
        
        return compacted
    
    def _tag_context_with_epistemology(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add epistemic tags to context items based on their nature
        """
        tagged = {}
        
        for key, value in context.items():
            if isinstance(value, dict):
                # Recursively tag nested dictionaries
                tagged[key] = self._tag_context_with_epistemology(value)
            elif isinstance(value, list):
                # Tag list items
                tagged_list = []
                for item in value:
                    if isinstance(item, dict):
                        tagged_list.append(self._tag_context_with_epistemology(item))
                    else:
                        tagged_list.append({
                            'content': item,
                            'epistemic_tag': self._infer_epistemic_tag(str(item))
                        })
                tagged[key] = tagged_list
            else:
                # Tag simple values
                tagged[key] = {
                    'content': value,
                    'epistemic_tag': self._infer_epistemic_tag(str(value))
                }
        
        return tagged
    
    def _infer_epistemic_tag(self, content: str) -> str:
        """
        Infer the appropriate epistemic tag for content
        """
        content_lower = content.lower()
        
        # Check for certainty markers
        if any(marker in content_lower for marker in ['fact:', 'according to', 'studies show', 'research indicates']):
            return EpistemicTag.CERTAIN_FACT.value
        
        # Check for probability markers
        if any(marker in content_lower for marker in ['likely', 'probably', 'possibly', 'might', 'may', 'could']):
            return EpistemicTag.PROBABLE_INFERENCE.value
        
        # Check for hypothetical markers
        if any(marker in content_lower for marker in ['if', 'suppose', 'assuming', 'hypothetically', 'imagine']):
            return EpistemicTag.HYPOTHETICAL.value
        
        # Check for uncertainty markers
        if any(marker in content_lower for marker in ['maybe', 'perhaps', 'uncertain', 'not sure', 'doubt']):
            return EpistemicTag.UNCERTAIN.value
        
        # Check for assumption markers
        if any(marker in content_lower for marker in ['assume', 'presume', 'working assumption', 'for the sake of argument']):
            return EpistemicTag.ASSUMPTION.value
        
        # Default to observation for direct statements
        return EpistemicTag.OBSERVATION.value
    
    def _perform_compaction(self, context: Dict[str, Any], target_size: int) -> Dict[str, Any]:
        """
        Perform actual compaction of the context
        """
        # Calculate current size estimate
        current_size = self._estimate_context_size(context)
        
        if current_size <= target_size:
            return context  # No compaction needed
        
        # Perform compaction by removing less important items
        compacted = self._remove_low_priority_items(context, target_size)
        
        return compacted
    
    def _estimate_context_size(self, context: Dict[str, Any]) -> int:
        """
        Estimate the size of the context in characters
        """
        return len(json.dumps(context, default=str))
    
    def _remove_low_priority_items(self, context: Dict[str, Any], target_size: int) -> Dict[str, Any]:
        """
        Remove low priority items until the context fits the target size
        """
        # This is a simplified implementation
        # In a real system, we'd have more sophisticated prioritization logic
        compacted = {}
        
        # Copy essential items first
        essential_keys = ['current_task', 'critical_info', 'important_context']
        for key in essential_keys:
            if key in context:
                compacted[key] = context[key]
        
        # Then copy remaining items until we approach the target size
        remaining_budget = target_size - self._estimate_context_size(compacted)
        
        for key, value in context.items():
            if key not in essential_keys and remaining_budget > 0:
                item_size = len(json.dumps({key: value}, default=str))
                if item_size < remaining_budget:
                    compacted[key] = value
                    remaining_budget -= item_size
        
        return compacted


class EpistemicTagger:
    """
    Class for managing epistemic tags and reasoning
    """
    
    def __init__(self):
        self.tag_weights = {
            EpistemicTag.CERTAIN_FACT.value: 1.0,
            EpistemicTag.PROBABLE_INFERENCE.value: 0.8,
            EpistemicTag.OBSERVATION.value: 0.7,
            EpistemicTag.ASSUMPTION.value: 0.5,
            EpistemicTag.HYPOTHETICAL.value: 0.3,
            EpistemicTag.UNCERTAIN.value: 0.2
        }
    
    def get_tag_weight(self, tag: str) -> float:
        """
        Get the weight/importance of an epistemic tag
        """
        return self.tag_weights.get(tag, 0.5)


def main():
    """
    Example usage of the cognitive load router
    """
    # Initialize the router
    router = MessageRouter()
    
    # Test messages of different cognitive loads
    test_messages = [
        "Hello",  # Tier 1: Light
        "What time is it?",  # Tier 1: Light
        "Can you explain how photosynthesis works?",  # Tier 2: Moderate
        "Analyze the economic impact of renewable energy adoption in developing countries, comparing costs, benefits, and implementation challenges across different regions",  # Tier 3: Heavy
        "Critical system failure detected. Immediate intervention required to prevent data loss and service disruption. Please prioritize this issue."  # Tier 4: Critical
    ]
    
    print("Testing Cognitive Load Router:")
    print("=" * 50)
    
    for i, msg in enumerate(test_messages, 1):
        print(f"\nTest {i}: '{msg}'")
        result = router.route_message(msg)
        print(f"  Tier: {result['cognitive_tier']}")
        print(f"  Intent: {result['intent_classification']['intent']}")
        print(f"  Confidence: {result['intent_classification']['confidence']:.2f}")
        print(f"  Disambiguated: {result['intent_classification']['disambiguation_applied']}")


if __name__ == "__main__":
    main()