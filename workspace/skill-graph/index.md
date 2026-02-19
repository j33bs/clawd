# Skill Graph Index

Entry point for the OpenClaw skill graph system.

## Overview

This skill graph implements the Zettelkasten method for AI agents - atomic notes linked together that create emergent knowledge.

## Core Primitives

- **Skills**: Individual markdown files with YAML frontmatter
- **Wikilinks**: `[[skill-name]]` links in prose that carry meaning
- **MOCs**: Maps of Content that organize clusters of related skills

## How It Works

1. **Progressive Disclosure**: Scan index → read descriptions → follow wikilinks → dive deep
2. **Traversal**: Agent reads index, understands the landscape, follows relevant paths
3. **Composition**: Small files compose into larger knowledge structures

## Quick Start

```python
from skill_graph import SkillGraph

graph = SkillGraph("/workspace/skill-graph")
skills = graph.scan()           # Get all skills
skill = graph.get("code-review") # Load specific skill
related = graph.traverse(skill)  # Get linked skills
```

## Available Skills

See individual skill files in `skills/` folder.

## MOCs (Maps of Content)

- [[mocs/development]] - Development workflow skills
- [[mocs/system]] - System administration skills
- [[mocs/research]] - Research and analysis skills

## The Philosophy

> "Single skill files can't hold deep knowledge. Skill graphs are the next step - instead of one injection, the agent navigates a knowledge structure, pulling in exactly what the current situation requires."

This is the difference between an agent that follows instructions and an agent that understands a domain.
