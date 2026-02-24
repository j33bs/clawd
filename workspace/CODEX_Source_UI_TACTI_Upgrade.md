# Codex Task: Upgrade Source UI to Reflect TACTI(C)-R Principles

## Context
The Source UI at http://127.0.0.1:19996 works but is "very generic". It should reflect the system's core identity and functionality.

## Current State
- Basic UI with sidebar, nav
- Static HTML/CSS/JS
- No TACTI(C)-R specific features

## Required Updates

### 1. Visual Identity (Theme)
- Replace generic styling with **TACTI(C)-R theme**
- Use the 5 principles as visual categories:
  - **AROUSAL** - Energy/fire/red
  - **TEMPORALITY** - Clock/time/blue  
  - **CROSS-TIMESCALE** - Layers/purple
  - **MALLEABILITY** - Morph/green
  - **AGENCY** - Autonomy/gold
- Custom logo/icon reflecting consciousness-inspired AI

### 2. Dashboard Panels (Functionality)
Add panels for core TACTI(C)-R modules:

| Panel | Module | Data |
|-------|--------|------|
| **Dream Consolidation** | `workspace/tacti_cr/dream_consolidation.py` | Memory consolidation status, last run |
| **Stigmergy Map** | `workspace/hivemind/hivemind/stigmergy.py` | Active pheromone marks, intensity |
| **Semantic Immune** | `workspace/tacti_cr/semantic_immune.py` | Quarantine stats, recent blocks |
| **Arousal Oscillator** | `workspace/tacti_cr/arousal_oscillator.py` | Current energy level, hourly histogram |
| **Trail Memory** | `workspace/hivemind/hivemind/trails.py` | Memory heatmap, recent trails |
| **HiveMind Peer Graph** | `workspace/hivemind/hivemind/peer_graph.py` | Agent connections visualization |
| **Skill Graph** | `workspace/skill-graph/` | Available skills, navigation |

### 3. Quick Actions
- **Run Dream Consolidation** button
- **Query Stigmergy** input
- **View Immune Status**  
- **Trigger Memory Trail**
- **Refresh Peer Graph**

### 4. Status Indicators
- QMD daemon health (port 8181)
- Knowledge base sync status
- Cron job health
- Memory usage

## Files to Modify
- `workspace/source-ui/index.html` - Add panels
- `workspace/source-ui/css/styles.css` - TACTI(C)-R theme
- `workspace/source-ui/js/app.js` - Panel logic
- `workspace/source-ui/api/` - Add backend endpoints

## Priority
1. Visual identity (quick win)
2. Status indicators (useful)
3. Dashboard panels (core feature)
4. Quick actions (automation)

---

# Bonus: Research Knowledge Graph Node Visualization

## Concept
Interactive node-based visualization for research data with dynamic intersection mapping.

## Features

### 1. Node Types
- **Topic Nodes** - Research topics (Active Inference, Slime Mold, etc.)
- **Intersection Nodes** - Where topics connect → high-value areas
- **User Input Nodes** - Generated from user interactions
- **Source Nodes** - Links to full texts/papers

### 2. Interactive Behaviors
- Click node → show summary + links to full texts
- Hover → preview info
- Drag to reposition
- User can add notes/annotations to nodes

### 3. Dynamic Intersection Mapping
- Track which topics user explores together
- Auto-generate intersection nodes when topics share usage
- Size/weight nodes by "value" (usage frequency, intersection count)
- Highlight valuable investigation areas

### 4. Data Sources
- `workspace/research/` - Paper data
- `workspace/memory/` - User research logs
- `workspace/knowledge_base/` - Indexed content

### 5. Visual Design
- Force-directed graph layout (D3.js or similar)
- Topic nodes = colored by TACTI(C)-R principle
- Intersection nodes = highlighted glow
- Zoom/pan controls
- Search/filter nodes

## Implementation
- Add `workspace/source-ui/panels/research-graph.js`
- Backend endpoint: `/api/research/graph`
- Frontend: D3.js force visualization

## Example Topics
- Active Inference
- Free Energy Principle  
- Physarum/Slime Mold
- Reservoir Computing
- Murmuration
- Integrated Information Theory
- Predictive Coding

## Notes
- Backend API exists: `workspace/source-ui/api/trails.py`
- Can read from existing TACTI(C)-R modules directly
- Keep it dark-themed (current style is good)
