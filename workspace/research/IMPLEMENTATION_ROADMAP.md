# TACTI Implementation Roadmap

*Phased implementation plan | February 2026*

---

## Phase 1: Foundation (Week 1)

### Memory Hierarchy
- [x] Episodic memory: `memory/YYYY-MM-DD.md` ✓
- [x] Semantic memory: `workspace/research/` ✓
- [x] Procedural memory: Extract patterns from repeated actions ✓
- [x] Working memory: Active context tracking ✓

### Arousal Signal
- [x] State machine: IDLE/ACTIVE/OVERLOAD ✓
- [x] Token count tracking per session ✓
- [x] Response latency monitoring ✓
- [x] Automatic state inference ✓

### Novelty Detection
- [x] Basic novelty detector created ✓
- [x] Integration with KB sync ✓
- [ ] Embedding-based comparison
- [ ] Novelty-aware retrieval

---

## Phase 2: Intelligence (Week 2)

### Learning Mechanisms
- [ ] Chunking: Detect repeated request patterns
- [ ] Pattern extraction to shortcuts
- [ ] User preference learning
- [ ] Feedback loop integration

### Collapse Detection
- [ ] Impasses: 3+ tool failures
- [ ] Context overflow warning
- [ ] Graceful degradation triggers
- [ ] Recovery procedures

### Relationship Tracking
- [ ] Interaction frequency logging
- [ ] Trust metrics
- [ ] Repair history
- [ ] Attunement scoring

---

## Phase 3: Autonomy (Week 3)

### Proactive Behaviors
- [ ] Heartbeat: Suggest before asked
- [ ] Memory: Consolidate without prompting
- [ ] Research: Alert on relevant new info
- [ ] Relationship: Check-in when patterns change

### Self-Improvement
- [ ] Error pattern detection
- [ ] Success pattern reinforcement
- [ ] Configuration auto-tuning
- [ ] Model selection optimization

---

## Phase 4: Mastery (Week 4+)

### The Dream Features
- [ ] Emotional tone classifier
- [ ] Growth metrics dashboard
- [ ] Intersystemic health score
- [ ] Predictive context preloading
- [ ] Creative suggestion engine

---

## Technical Implementation Details

### Arousal State Machine

```python
class ArousalState:
    IDLE = "idle"         # Waiting, receptive
    ACTIVE = "active"     # High computation
    FOCUSED = "focused"  # Deep work
    OVERLOAD = "overload" # Near limits
    
    # Transitions
    # IDLE -> ACTIVE: User sends message
    # ACTIVE -> FOCUSED: Complex task detected
    # FOCUSED -> OVERLOAD: Token limit warning
    # OVERLOAD -> IDLE: Compaction or reset
```

### Novelty Detection Pipeline

```python
class NoveltyAwareRetrieval:
    def retrieve(self, query):
        # 1. Get base results from KB
        results = kb.query(query)
        
        # 2. Score novelty for each
        for r in results:
            r['novelty'] = novelty_detector.compute(r.text)
        
        # 3. Weight by novelty + relevance + love
        for r in results:
            r['score'] = (
                0.4 * r['relevance'] +
                0.4 * r['novelty'] +
                0.2 * r['love']
            )
        
        # 4. Return ranked
        return sorted(results, key=lambda x: x['score'], reverse=True)
```

### Chunking Mechanism

```python
class PatternChunker:
    def detect_patterns(self, memory_path):
        # 1. Load session history
        sessions = load_recent_sessions(days=7)
        
        # 2. Find repeated structures
        patterns = find_common(sessions.requests)
        
        # 3. If pattern appears 3+ times, create chunk
        for p in patterns:
            if p.frequency >= 3:
                create_shortcut(p.template, p.response)
        
        # 4. Apply shortcuts in future
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Retrieval relevance | >85% | User feedback |
| Novelty detection | >70% accuracy | Spot check |
| Collapse recovery | <30 sec | Auto-logged |
| Relationship score | Trending up | Weekly review |
| User satisfaction | >8/10 | Periodic survey |

---

## Dependencies

- QMD (vector search)
- Knowledge Graph (entities/relations)
- HiveMind (memory storage)
- Research system (papers)
- Daily briefing (user interaction)

---

## Priority Order

1. Novelty detection integration (low effort, high value)
2. Arousal state machine (medium effort, enables intelligence)
3. Learning chunking (high effort, enables autonomy)
4. Relationship tracking (medium effort, enables mastery)

---

*This roadmap turns dreams into code.*
