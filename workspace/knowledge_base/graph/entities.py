"""
Entity Extraction
Simple keyword-based entity extraction from text
"""
import re
from typing import List, Dict, Set


# Common entity patterns
ENTITY_PATTERNS = {
    "model": [
        r"(?:model|llm|AI|GPT|Claude|Qwen|Groq|MiniMax|Ollama|Gemini)",
        r"(?:qwen|llama|gpt|claude|gemini|deepseek)",
    ],
    "system": [
        r"(?:OpenClaw|HiveMind|QMD|Moltbook)",
    ],
    "provider": [
        r"(?:provider|backend|API)",
    ],
    "file": [
        r"(?:\.md|\.js|\.py|\.json|\.yaml|\.yml)",
    ],
    "command": [
        r"(?:npx|python|bash|git|npm|node)",
    ],
}


def extract_entities(text: str) -> List[str]:
    """Extract entities from text using simple pattern matching."""
    entities = []
    text_lower = text.lower()
    
    # Extract system names
    systems = ["openclaw", "hivemind", "qmd", "moltbook", "tacti(c)-r"]
    for s in systems:
        if s in text_lower:
            entities.append(f"system:{s}")
    
    # Extract model names
    models = ["qwen", "llama", "gpt", "claude", "gemini", "groq", "minimax", "ollama"]
    for m in models:
        if m in text_lower:
            entities.append(f"model:{m}")
    
    # Extract providers
    providers = ["google", "anthropic", "openai", "meta", "qwen-portal", "groq"]
    for p in providers:
        if p in text_lower:
            entities.append(f"provider:{p}")
    
    # Extract technical terms
    technical = [
        "routing", "fallback", "memory", "embedding", "vector",
        "bm25", "rerank", "mcp", "agent", "cron", "heartbeat"
    ]
    for t in technical:
        if t in text_lower:
            entities.append(f"term:{t}")
    
    return list(set(entities))


def extract_decision_markers(text: str) -> bool:
    """Check if text contains decision markers."""
    markers = [
        "decided", "decision", "chose", "chosen",
        "will use", "going to", "plan to",
        "agreed", "approved", "confirmed"
    ]
    text_lower = text.lower()
    return any(m in text_lower for m in markers)


def extract_lesson_markers(text: str) -> bool:
    """Check if text contains lesson markers."""
    markers = [
        "learned", "lesson", "insight", "found that",
        "discovered", "realized", "figured out",
        "mistake", "error", "bug", "fix"
    ]
    text_lower = text.lower()
    return any(m in text_lower for m in markers)


def classify_knowledge_type(text: str) -> str:
    """Classify the type of knowledge in text."""
    if extract_decision_markers(text):
        return "decision"
    elif extract_lesson_markers(text):
        return "lesson"
    elif text.startswith("#") or "## " in text:
        return "procedure"
    else:
        return "fact"


def extract_relationships(text: str, entities: List[str]) -> List[Dict]:
    """Extract relationships between entities."""
    relationships = []
    
    # Look for common relationship patterns
    if "depends on" in text.lower():
        for e1 in entities:
            for e2 in entities:
                if e1 != e2:
                    relationships.append({
                        "from": e1,
                        "to": e2,
                        "type": "depends_on"
                    })
    
    if "caused by" in text.lower():
        for e1 in entities:
            for e2 in entities:
                if e1 != e2:
                    relationships.append({
                        "from": e1,
                        "to": e2,
                        "type": "caused_by"
                    })
    
    if "related to" in text.lower():
        for e1 in entities:
            for e2 in entities:
                if e1 != e2:
                    relationships.append({
                        "from": e1,
                        "to": e2,
                        "type": "related_to"
                    })
    
    return relationships


def extract_key_phrases(text: str, max_phrases: int = 5) -> List[str]:
    """Extract key phrases from text."""
    # Simple extraction: capitalized phrases and important terms
    phrases = []
    
    # Capitalized phrases (potential proper nouns)
    caps = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
    phrases.extend(caps[:3])
    
    # Important terms
    important = ["routing", "memory", "model", "provider", "config", "fallback", "agent"]
    for imp in important:
        if imp in text.lower():
            phrases.append(imp)
    
    return list(set(phrases))[:max_phrases]
