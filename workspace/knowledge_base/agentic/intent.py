"""
Intent Classification
Determines the best retrieval strategy for a query
"""
import re
from typing import Dict, List


# Intent patterns
INTENT_PATTERNS = {
    "search_workspace": [
        r"find (?:me )?(?:the |a )?(?:file|doc|document|code)",
        r"where (?:is|are) (?:the |a )?",
        r"search (?:for |)",
        r"look (?:up |)",
    ],
    "decision_lookup": [
        r"what (?:did we|do we) (?:decide|decide on|choose|agree)",
        r"why (?:did we|did we|do we)",
        r"what was the (?:reason|decision)",
        r"remember when",
        r"past (?:decision|choice)",
    ],
    "memory_lookup": [
        r"what do we know about",
        r"tell me about",
        r"what (?:have|do) we know",
        r"context (?:about|on)",
    ],
    "procedure_lookup": [
        r"how do (?:I|we|you)",
        r"how to",
        r"what(?:'s| is) the (?:process|steps|way to)",
        r"guide (?:for|to)",
    ],
    "comparison": [
        r"(?:compare|versus|vs\.? |difference between)",
        r"(?:better|prefer|recommend)",
        r"which (?:is|should|would)",
    ],
    "entity_lookup": [
        r"tell me (?:the|about) (.+)",
        r"what (?:is|are) (.+)",
        r"explain (.+)",
    ],
}


def classify_intent(query: str) -> Dict:
    """
    Classify query intent and determine best retrieval strategy.
    
    Returns:
        {
            "strategy": "search" | "graph" | "memory" | "hybrid",
            "confidence": 0.0-1.0,
            "filters": [],
            "steps": []
        }
    """
    query_lower = query.lower()
    
    # Check each intent pattern
    matched_intents = []
    for intent_name, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, query_lower):
                matched_intents.append(intent_name)
                break
    
    # Determine strategy based on intent
    if not matched_intents:
        # Default: try everything
        return {
            "strategy": "hybrid",
            "confidence": 0.5,
            "intents": [],
            "steps": ["qmd_search", "hivemind_query", "graph_search"]
        }
    
    # Build strategy based on matched intents
    steps = []
    filters = []
    
    if "search_workspace" in matched_intents:
        steps.append("qmd_search")
        filters.append("file")
    
    if "decision_lookup" in matched_intents:
        steps.append("graph_search")
        steps.append("hivemind_query")
        filters.append("decision")
    
    if "memory_lookup" in matched_intents:
        steps.append("hivemind_query")
        filters.append("fact")
    
    if "procedure_lookup" in matched_intents:
        steps.append("qmd_search")
        filters.append("procedure")
    
    # If only one intent, add fallback
    if len(steps) == 1:
        steps.append("fallback")
    
    return {
        "strategy": "hybrid" if len(steps) > 1 else steps[0] if steps else "qmd_search",
        "confidence": min(0.5 + (len(matched_intents) * 0.15), 0.95),
        "intents": matched_intents,
        "filters": filters,
        "steps": steps
    }


def extract_entities_from_query(query: str) -> List[str]:
    """Extract entity names from the query."""
    entities = []
    
    # Model names
    models = ["qwen", "llama", "gpt", "claude", "gemini", "groq", "minimax", "ollama"]
    query_lower = query.lower()
    for m in models:
        if m in query_lower:
            entities.append(m)
    
    # System names
    systems = ["openclaw", "hivemind", "qmd", "moltbook", "telegram"]
    for s in systems:
        if s in query_lower:
            entities.append(s)
    
    return entities


def build_search_query(query: str) -> str:
    """Build optimized search query from user input."""
    # Remove question words
    cleaned = re.sub(r'\b(what|how|why|when|where|who|which)\b', '', query.lower())
    cleaned = re.sub(r'\b(is|are|do|does|can|should|would)\b', '', cleaned)
    cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
    cleaned = ' '.join(cleaned.split())
    
    return cleaned or query
