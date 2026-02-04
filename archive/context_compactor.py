#!/usr/bin/env python3
"""
Reflexive Context Compaction with Epistemic Tagging
Implements semantic compression that preserves claims, warrants, and unresolved questions
"""

import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class EpistemicTag(Enum):
    """Types of epistemic elements to preserve during compaction"""
    CLAIM = "claim"
    WARRANT = "warrant" 
    QUESTION = "question"
    EVIDENCE = "evidence"
    ASSUMPTION = "assumption"
    UNCERTAINTY = "uncertainty"
    DECISION = "decision"
    GOAL = "goal"


@dataclass
class EpistemicElement:
    """Represents a preserved element in compacted context"""
    type: EpistemicTag
    content: str
    importance: float  # 0.0 to 1.0
    relevance: float   # 0.0 to 1.0
    timestamp: Optional[float] = None
    source: Optional[str] = None


class ContextCompactor:
    """
    Implements reflexive context compaction with epistemic tagging
    Preserves semantic meaning rather than just truncating text
    """
    
    def __init__(self):
        self.patterns = {
            EpistemicTag.CLAIM: [
                r"(?:this suggests|it appears|the evidence shows|research indicates|studies show)\s+(.+?)[\.!?]",
                r"(?:I believe|we think|it seems|apparently)\s+(.+?)[\.!?]",
            ],
            EpistemicTag.WARRANT: [
                r"(?:because|since|due to|given that|owing to)\s+(.+?)[\.!?]",
                r"(?:this is important because|the reason is|the justification is)\s+(.+?)[\.!?]",
            ],
            EpistemicTag.QUESTION: [
                r"\b(how|why|what|when|where|who)\s+\w+.+?\?",
                r"(?:can we|is it possible|would it be|could we)\s+(.+?)[\.!?]",
            ],
            EpistemicTag.EVIDENCE: [
                r"(?:according to|as shown by|based on)\s+(.+?)(?:\.|,|and)",
                r"(?:the data shows|the study found|results indicate)\s+(.+?)[\.!?]",
            ],
            EpistemicTag.ASSUMPTION: [
                r"(?:assuming|presuming|if we assume|provided that)\s+(.+?)[\.!?]",
                r"(?:we assume|it is assumed|the assumption is)\s+(.+?)[\.!?]",
            ],
            EpistemicTag.UNCERTAINTY: [
                r"(?:maybe|perhaps|possibly|potentially|might|could be|seems|appears|likely|unlikely)\s*(.+?)[\.!?]",
                r"(?:it's unclear|unknown|not sure|uncertain|ambiguous)\s+(.+?)[\.!?]",
            ],
            EpistemicTag.DECISION: [
                r"(?:we decided|the decision was|we chose|it was decided)\s+(.+?)[\.!?]",
                r"(?:therefore|thus|consequently|accordingly)\s+(.+?)[\.!?]",
            ],
            EpistemicTag.GOAL: [
                r"(?:our goal is|we aim to|the objective is|we want to achieve)\s+(.+?)[\.!?]",
                r"(?:to achieve|in order to|for the purpose of)\s+(.+?)[\.!?]",
            ]
        }
    
    def extract_epistemic_elements(self, text: str) -> List[EpistemicElement]:
        """Extract epistemic elements from text using pattern matching"""
        elements = []
        
        for tag_type, patterns in self.patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    content = match.group(0) if match.group(0) else match.group(1) if match.groups() else ""
                    if content.strip():
                        # Calculate basic importance/relevance scores
                        importance = self._calculate_importance(content, tag_type)
                        relevance = self._calculate_relevance(content)
                        
                        element = EpistemicElement(
                            type=tag_type,
                            content=content.strip(),
                            importance=importance,
                            relevance=relevance
                        )
                        elements.append(element)
        
        # Also extract standalone questions that might not match patterns
        standalone_questions = re.findall(r"[^\.!?]*\?.+?(?=[\.!?]|$)", text)
        for question in standalone_questions:
            if question.strip():
                element = EpistemicElement(
                    type=EpistemicTag.QUESTION,
                    content=question.strip(),
                    importance=0.8,  # Questions tend to be important
                    relevance=0.7
                )
                elements.append(element)
        
        # Sort by combined importance score
        elements.sort(key=lambda x: x.importance * x.relevance, reverse=True)
        
        return elements
    
    def _calculate_importance(self, content: str, tag_type: EpistemicTag) -> float:
        """Calculate importance score based on content and tag type"""
        base_importance = {
            EpistemicTag.DECISION: 0.9,
            EpistemicTag.QUESTION: 0.8,
            EpistemicTag.GOAL: 0.8,
            EpistemicTag.ASSUMPTION: 0.7,
            EpistemicTag.CLAIM: 0.6,
            EpistemicTag.EVIDENCE: 0.7,
            EpistemicTag.WARRANT: 0.6,
            EpistemicTag.UNCERTAINTY: 0.5
        }.get(tag_type, 0.5)
        
        # Boost for longer content (more likely to be substantial)
        length_factor = min(len(content.split()) / 50.0, 1.0)
        
        # Boost for content with specific markers
        certainty_markers = ["therefore", "consequently", "thus", "hence", "accordingly"]
        certainty_boost = 0.2 if any(marker in content.lower() for marker in certainty_markers) else 0
        
        return min(base_importance + length_factor * 0.2 + certainty_boost, 1.0)
    
    def _calculate_relevance(self, content: str) -> float:
        """Calculate relevance score based on content characteristics"""
        # Higher relevance for content with action verbs or specific entities
        action_verbs = ["implement", "create", "develop", "analyze", "research", "build", "design"]
        entity_indicators = ["this", "that", "these", "those", "here", "now"]
        
        action_score = 0.3 if any(verb in content.lower() for verb in action_verbs) else 0
        entity_score = 0.2 if any(indicator in content.lower() for indicator in entity_indicators) else 0
        
        return min(0.5 + action_score + entity_score, 1.0)
    
    def compact_context(self, text: str, target_length: int = 1000, 
                       min_elements: int = 5) -> Dict[str, Any]:
        """Compact context while preserving epistemic elements"""
        original_length = len(text)
        
        # Extract all epistemic elements
        elements = self.extract_epistemic_elements(text)
        
        # Sort by importance * relevance to prioritize the most important elements
        sorted_elements = sorted(elements, key=lambda x: x.importance * x.relevance, reverse=True)
        
        # Take top elements up to the minimum required
        selected_elements = sorted_elements[:max(min_elements, len(sorted_elements))]
        
        # Build compacted text
        compacted_parts = []
        remaining_length = target_length
        
        for element in selected_elements:
            element_text = f"[{element.type.value.upper()}]: {element.content}"
            
            # Check if adding this element would exceed target length
            if len(element_text) <= remaining_length:
                compacted_parts.append(element_text)
                remaining_length -= len(element_text)
            else:
                # If we're tight on space, take a portion of the element
                if remaining_length > 20:  # At least 20 chars for meaningful text
                    truncated = element_text[:remaining_length-3] + "..."
                    compacted_parts.append(truncated)
                    break
        
        compacted_text = "\n".join(compacted_parts)
        
        return {
            "original_length": original_length,
            "compacted_length": len(compacted_text),
            "compression_ratio": len(compacted_text) / original_length if original_length > 0 else 0,
            "elements_extracted": len(elements),
            "elements_preserved": len(selected_elements),
            "compacted_text": compacted_text,
            "preserved_elements": [
                {
                    "type": elem.type.value,
                    "content": elem.content,
                    "importance": elem.importance,
                    "relevance": elem.relevance
                } for elem in selected_elements
            ]
        }
    
    def expand_compacted_context(self, compacted_data: Dict[str, Any]) -> str:
        """Expand compacted context back to readable form"""
        expanded_parts = ["Expanded Context from Compacted Form:"]
        
        for element in compacted_data.get("preserved_elements", []):
            expanded_parts.append(f"{element['type'].upper()}: {element['content']}")
        
        return "\n\n".join(expanded_parts)


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python context_compactor.py \"text to compact\" [target_length]")
        sys.exit(1)
    
    text = " ".join(sys.argv[1:-1]) if len(sys.argv) > 2 else " ".join(sys.argv[1:])
    target_length = int(sys.argv[-1]) if len(sys.argv) > 2 else 1000
    
    compactor = ContextCompactor()
    result = compactor.compact_context(text, target_length)
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    # Example usage
    example_text = """
    We believe that implementing a tiered cognitive-load routing system would significantly improve performance. 
    This is important because it allows us to preserve quota and reduce latency. However, we're uncertain about 
    whether the local model would be powerful enough for complex tasks. Studies show that local processing can 
    handle up to 70% of common requests efficiently. Our goal is to create a system that keeps the "thinking 
    surface" close to the machine. We decided to implement this because the current system relies too heavily 
    on cloud models. The question remains: how do we balance between local and cloud processing? Perhaps we 
    should consider using Ollama for local LLM processing. According to best practices, we should implement 
    constraint-aware prompt synthesis. We assume that users will benefit from faster response times.
    """
    
    compactor = ContextCompactor()
    result = compactor.compact_context(example_text, target_length=500)
    
    print("Original length:", len(example_text))
    print("Compacted length:", result["compacted_length"])
    print("Compression ratio:", result["compression_ratio"])
    print("\nCompacted text:")
    print(result["compacted_text"])
    print("\nPreserved elements:")
    for elem in result["preserved_elements"]:
        print(f"- {elem['type']}: {elem['content'][:60]}...")