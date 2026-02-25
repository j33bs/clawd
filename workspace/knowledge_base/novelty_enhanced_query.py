#!/usr/bin/env python3
"""
Novelty-Enhanced Query
Wraps kb.py query with novelty scoring.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Import the novelty detector
sys.path.insert(0, str(Path(__file__).parent))
from novelty import NoveltyDetector

# Import the KB query logic
sys.path.insert(0, str(Path(__file__).parent))
from agentic.retrieve import multi_step_retrieve
from agentic.synthesize import synthesize_response
from agentic.intent import classify_intent


def query_with_novelty(query_text, agent=None, novelty_weight=0.3):
    """
    Query the KB and score results by novelty.
    
    novelty_weight: 0.0 = ignore novelty, 1.0 = novelty only
    """
    # Get standard results
    intent = classify_intent(query_text)
    results = multi_step_retrieve(query_text, intent, agent)
    
    # Initialize novelty detector
    detector = NoveltyDetector()
    
    # Score each result by novelty + relevance
    for r in results:
        novelty = detector.compute_novelty(r.get('text', ''))
        original_score = r.get('score', 0.5)
        
        # Blend novelty with original score
        r['novelty_score'] = novelty
        r['original_score'] = original_score
        r['score'] = (1 - novelty_weight) * original_score + novelty_weight * novelty
    
    # Re-rank by combined score
    results.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    # Synthesize with novelty-aware results
    response = synthesize_response(query_text, results, intent)
    
    return {
        'answer': response['answer'],
        'results': results,
        'citations': response.get('citations', []),
        'sources': response.get('sources', [])
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python novelty_enhanced_query.py '<query>'")
        sys.exit(1)
    
    query = ' '.join(sys.argv[1:])
    print(f"🔍 Querying with novelty detection: {query}\n")
    
    result = query_with_novelty(query)
    
    print("=" * 50)
    print("📚 ANSWER (Novelty-Enhanced)")
    print("=" * 50)
    print(result['answer'])
    
    if result.get('citations'):
        print("\n📋 CITATIONS")
        for cit in result['citations']:
            print(f"  - {cit}")
    
    print("\n🔬 NOVELTY SCORES (top 3)")
    for r in result['results'][:3]:
        print(f"  {r.get('novelty_score', 0):.2f} - {r.get('text', '')[:60]}...")
