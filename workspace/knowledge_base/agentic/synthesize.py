"""
Response Synthesis
Generates final response with citations from retrieval results
"""
from typing import Dict, List, Any


def synthesize_response(query: str, results: Dict, intent: Dict) -> Dict:
    """
    Synthesize a response from retrieval results.
    
    Returns:
        {
            "answer": "...",
            "citations": [...],
            "sources": [...],
            "confidence": 0.0-1.0
        }
    """
    combined = results.get("combined", [])
    
    if not combined:
        return {
            "answer": "I couldn't find any relevant information in the knowledge base. Try rephrasing your question or adding more context.",
            "citations": [],
            "sources": [],
            "confidence": 0.0
        }
    
    # Extract content from results
    contents = []
    citations = []
    sources = []
    
    for r in combined:
        content = r.get("content", "")
        if content and len(content) > 20:
            contents.append(content)
            
            # Build citation
            if r.get("source") == "qmd":
                path = r.get("path", r.get("title", ""))
                citations.append(f"QMD: {path} ({r.get('score', 0)*100:.0f}%)")
                sources.append(path)
            elif r.get("source") == "hivemind":
                kind = r.get("type", "memory")
                scope = r.get("scope", "shared")
                citations.append(f"HiveMind: {kind} [{scope}]")
                sources.append(f"memory:{kind}")
            elif r.get("source") == "graph":
                citations.append("Knowledge Graph")
                sources.append("graph")
    
    # Build answer based on intent
    answer = build_answer(query, contents, intent)
    
    # Calculate confidence
    confidence = calculate_confidence(contents, intent)
    
    return {
        "answer": answer,
        "citations": citations[:5],  # Limit citations
        "sources": sources[:5],
        "confidence": confidence
    }


def build_answer(query: str, contents: List[str], intent: Dict) -> str:
    """Build a natural language answer from contents."""
    if not contents:
        return "No relevant information found."
    
    # Check if this is a specific lookup
    query_lower = query.lower()
    
    if "what" in query_lower and "decide" in query_lower:
        # Decision lookup
        decision_contents = [c for c in contents if any(
            m in c.lower() for m in ["decide", "decision", "chose", "agreed"]
        )]
        if decision_contents:
            return summarize_content(decision_contents[0], "decision")
    
    if "how" in query_lower or "what" in query_lower:
        # Look for procedure or explanation
        if contents:
            return summarize_content(contents[0], "explanation")
    
    # Default: combine top contents
    return combine_contents(contents[:3])


def summarize_content(content: str, mode: str = "general") -> str:
    """Summarize content for response."""
    # Take first 300 chars and clean up
    summary = content[:300]
    
    # Try to end at a sentence boundary
    for end in ['. ', '! ', '? ']:
        last = summary.rfind(end)
        if last > 100:
            summary = summary[:last + 1]
            break
    
    if len(content) > len(summary):
        summary += "..."
    
    return summary


def combine_contents(contents: List[str]) -> str:
    """Combine multiple content pieces into a coherent answer."""
    if not contents:
        return "No information available."
    
    if len(contents) == 1:
        return summarize_content(contents[0])
    
    # Find common topics
    combined = []
    seen_topics = set()
    
    for content in contents:
        # Take first part of each
        part = content[:150]
        
        # Avoid duplicates
        topic = part[:30].lower()
        if topic not in seen_topics:
            combined.append(part)
            seen_topics.add(topic)
    
    if combined:
        return " | ".join(combined)[:400] + ("..." if sum(len(c) for c in combined) > 400 else "")
    
    return summarize_content(contents[0])


def calculate_confidence(contents: List[str], intent: Dict) -> float:
    """Calculate confidence score based on results."""
    if not contents:
        return 0.0
    
    base_confidence = 0.5
    
    # More content = higher confidence
    if len(contents) >= 3:
        base_confidence += 0.2
    elif len(contents) >= 2:
        base_confidence += 0.1
    
    # Higher intent confidence
    intent_conf = intent.get("confidence", 0.5)
    base_confidence = (base_confidence + intent_conf) / 2
    
    # Penalize short content
    avg_length = sum(len(c) for c in contents) / len(contents)
    if avg_length < 50:
        base_confidence -= 0.2
    
    return min(max(base_confidence, 0.0), 1.0)


def format_citations(citations: List[str]) -> str:
    """Format citations for display."""
    if not citations:
        return ""
    
    lines = ["**Sources:**"]
    for cit in citations:
        lines.append(f"- {cit}")
    
    return "\n".join(lines)
