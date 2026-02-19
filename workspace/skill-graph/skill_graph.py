#!/usr/bin/env python3
"""
Skill Graph - Zettelkasten-style knowledge management for AI agents.

Usage:
    python skill_graph.py scan           # List all skills
    python skill_graph.py get <name>     # Get a specific skill
    python skill_graph.py traverse <name> # Get skill + linked skills
"""

import os
import re
import sys
from pathlib import Path
from typing import Any
import json
import yaml


class SkillGraph:
    """A skill graph system with wikilinks and progressive disclosure."""
    
    def __init__(self, root: str):
        self.root = Path(root)
        self.skills_dir = self.root / "skills"
        self.mocs_dir = self.root / "mocs"
        self.index = self.root / "index.md"
        self._cache: dict[str, dict[str, Any]] = {}
    
    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """Extract YAML frontmatter and remaining content."""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    return frontmatter, parts[2].strip()
                except yaml.YAMLError:
                    pass
        return {}, content
    
    def _extract_wikilinks(self, content: str) -> list[str]:
        """Extract [[wikilinks]] from content."""
        pattern = r'\[\[([^\]]+)\]\]'
        return re.findall(pattern, content)
    
    def load_skill(self, name: str) -> dict[str, Any]:
        """Load a skill by name."""
        if name in self._cache:
            return self._cache[name]
        
        # Try skills directory
        skill_file = self.skills_dir / f"{name}.md"
        if not skill_file.exists():
            # Try MOC directory
            skill_file = self.mocs_dir / f"{name}.md"
        
        if not skill_file.exists():
            raise FileNotFoundError(f"Skill '{name}' not found")
        
        content = skill_file.read_text()
        frontmatter, body = self._parse_frontmatter(content)
        wikilinks = self._extract_wikilinks(body)
        
        skill = {
            "name": name,
            "file": str(skill_file),
            "description": frontmatter.get("description", ""),
            "tags": frontmatter.get("tags", []),
            "links": frontmatter.get("links", []) + wikilinks,
            "content": body,
        }
        
        self._cache[name] = skill
        return skill
    
    def scan(self) -> list[dict[str, Any]]:
        """Scan all skills in the graph."""
        skills = []
        
        # Scan skills
        if self.skills_dir.exists():
            for f in self.skills_dir.glob("*.md"):
                name = f.stem
                try:
                    skill = self.load_skill(name)
                    skills.append({
                        "name": name,
                        "description": skill["description"],
                        "tags": skill["tags"],
                        "links": skill["links"],
                    })
                except Exception as e:
                    print(f"Error loading {name}: {e}", file=sys.stderr)
        
        # Scan MOCs
        if self.mocs_dir.exists():
            for f in self.mocs_dir.glob("*.md"):
                name = f"mocs/{f.stem}"
                try:
                    # Load MOC directly
                    content = f.read_text()
                    frontmatter, body = self._parse_frontmatter(content)
                    skills.append({
                        "name": name,
                        "description": frontmatter.get("description", ""),
                        "type": "moc",
                        "links": self._extract_wikilinks(body),
                    })
                except Exception as e:
                    print(f"Error loading {name}: {e}", file=sys.stderr)
        
        return sorted(skills, key=lambda x: x["name"])
    
    def traverse(self, name: str, depth: int = 1) -> dict[str, Any]:
        """Get a skill and its linked skills."""
        skill = self.load_skill(name)
        result = {
            "skill": skill,
            "linked": [],
        }
        
        if depth > 0:
            for link in skill["links"]:
                try:
                    linked_skill = self.load_skill(link)
                    result["linked"].append({
                        "name": link,
                        "description": linked_skill["description"],
                    })
                except FileNotFoundError:
                    result["linked"].append({
                        "name": link,
                        "error": "not found",
                    })
        
        return result
    
    def search(self, query: str) -> list[dict[str, Any]]:
        """Search skills by name, description, or tags."""
        results = []
        query_lower = query.lower()
        
        for skill in self.scan():
            # Check name
            if query_lower in skill["name"].lower():
                results.append(skill)
                continue
            
            # Check description
            if query_lower in skill.get("description", "").lower():
                results.append(skill)
                continue
            
            # Check tags
            for tag in skill.get("tags", []):
                if query_lower in tag.lower():
                    results.append(skill)
                    break
        
        return results


def cmd_scan(graph: SkillGraph):
    """List all skills."""
    skills = graph.scan()
    print(f"# Skill Graph: {len(skills)} items\n")
    
    # Group by type
    mocs = [s for s in skills if s.get("type") == "moc"]
    regular = [s for s in skills if s.get("type") != "moc"]
    
    if mocs:
        print("## Maps of Content (MOCs)")
        for s in mocs:
            print(f"  [[{s['name']}]] - {s.get('description', '')}")
        print()
    
    print("## Skills")
    for s in regular:
        tags = f" [{', '.join(s.get('tags', []))}]" if s.get("tags") else ""
        print(f"  - {s['name']}{tags}")
        if s.get("description"):
            print(f"    {s['description'][:60]}...")


def cmd_get(graph: SkillGraph, name: str):
    """Get a specific skill."""
    try:
        skill = graph.load_skill(name)
        print(f"# {skill['name']}")
        print(f"\n{skill['description']}")
        print(f"\nTags: {', '.join(skill['tags'])}")
        print(f"Links: {', '.join(skill['links'])}")
        print("\n--- Content ---")
        print(skill["content"])
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_traverse(graph: SkillGraph, name: str):
    """Traverse skill and its links."""
    result = graph.traverse(name, depth=1)
    skill = result["skill"]
    
    print(f"# {skill['name']}")
    print(f"\n{skill['description']}")
    print(f"\n## Linked Skills")
    for link in result["linked"]:
        if "error" in link:
            print(f"  - [[{link['name']}]] (not found)")
        else:
            print(f"  - [[{link['name']}]] - {link['description']}")
    
    if skill["links"]:
        print(f"\n## All Links: {', '.join(skill['links'])}")


def cmd_search(graph: SkillGraph, query: str):
    """Search skills."""
    results = graph.search(query)
    print(f"# Search: '{query}' ({len(results)} results)\n")
    for r in results:
        print(f"  - {r['name']}")
        if r.get("description"):
            print(f"    {r['description'][:80]}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    # Default to workspace/skill-graph
    root = os.environ.get("SKILL_GRAPH_ROOT", "/home/jeebs/src/clawd/workspace/skill-graph")
    graph = SkillGraph(root)
    
    cmd = sys.argv[1]
    
    if cmd == "scan":
        cmd_scan(graph)
    elif cmd == "get" and len(sys.argv) >= 3:
        cmd_get(graph, sys.argv[2])
    elif cmd == "traverse" and len(sys.argv) >= 3:
        cmd_traverse(graph, sys.argv[2])
    elif cmd == "search" and len(sys.argv) >= 3:
        cmd_search(graph, sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
