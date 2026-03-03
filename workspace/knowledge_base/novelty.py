#!/usr/bin/env python3
"""
Novelty Detection Module
Compares new content against existing embeddings to detect novelty.
"""
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple

class NoveltyDetector:
    def __init__(self, entities_path: str = None):
        self.entities_path = entities_path or Path(__file__).parent / "data" / "entities.jsonl"
        self.existing_chunks = []
        self._load_existing()
    
    def _load_existing(self):
        """Load existing entities/chunks from KB."""
        if not Path(self.entities_path).exists():
            return
        with open(self.entities_path) as f:
            for line in f:
                try:
                    self.existing_chunks.append(json.loads(line))
                except:
                    pass
    
    def compute_novelty(self, text: str, embedding: np.ndarray = None) -> float:
        """
        Compute novelty score (0-1) for new text.
        0 = identical to existing
        1 = completely novel
        """
        if not self.existing_chunks:
            return 1.0  # No existing content, everything is novel
        
        # Simple heuristic: check text similarity via common words
        new_words = set(text.lower().split())
        
        max_similarity = 0.0
        for chunk in self.existing_chunks:
            existing_text = chunk.get('text', '').lower()
            existing_words = set(existing_text.split())
            
            if not existing_words:
                continue
            
            # Jaccard similarity
            intersection = len(new_words & existing_words)
            union = len(new_words | existing_words)
            similarity = intersection / union if union > 0 else 0
            
            max_similarity = max(max_similarity, similarity)
        
        # Novelty is inverse of similarity
        return 1.0 - max_similarity
    
    def is_novel(self, text: str, threshold: float = 0.7) -> bool:
        """Check if text is novel enough (above threshold)."""
        return self.compute_novelty(text) >= threshold
    
    def rank_by_novelty(self, chunks: List[Dict]) -> List[Dict]:
        """Rank chunks by novelty score."""
        for chunk in chunks:
            chunk['novelty'] = self.compute_novelty(chunk.get('text', ''))
        return sorted(chunks, key=lambda x: x.get('novelty', 0), reverse=True)


if __name__ == "__main__":
    detector = NoveltyDetector()
    
    # Test
    test_texts = [
        "TACTI is a framework for agent architecture",
        "The weather is sunny today",
        "Agentic Design Patterns from arXiv 2026"
    ]
    
    for text in test_texts:
        novelty = detector.compute_novelty(text)
        print(f"Novelty: {novelty:.2f} - {text[:50]}...")
