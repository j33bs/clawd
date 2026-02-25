#!/usr/bin/env python3
"""
Pattern Chunker
Detects repeated patterns in user requests and creates shortcuts.
"""
import json
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

class PatternChunker:
    def __init__(self, memory_dir="memory/", shortcuts_path="workspace/memory/shortcuts.json"):
        self.memory_dir = Path(memory_dir)
        self.shortcuts_path = Path(shortcuts_path)
        self.shortcuts = self._load_shortcuts()
    
    def _load_shortcuts(self):
        if self.shortcuts_path.exists():
            with open(self.shortcuts_path) as f:
                return json.load(f)
        return {"shortcuts": []}
    
    def _save_shortcuts(self):
        with open(self.shortcuts_path, 'w') as f:
            json.dump(self.shortcuts, f, indent=2)
    
    def _extract_template(self, text):
        """Extract a template by replacing specific values with placeholders."""
        # Replace numbers
        template = re.sub(r'\d+', '<N>', text)
        # Replace paths
        template = re.sub(r'/[\w/]+', '<PATH>', template)
        # Replace UUIDs
        template = re.sub(r'[a-f0-9-]{8,}', '<ID>', template)
        return template.lower().strip()
    
    def scan_sessions(self, days=7):
        """Scan recent sessions for patterns."""
        patterns = Counter()
        
        # Read recent daily files
        today = datetime.now()
        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            memory_file = self.memory_dir / f"{date_str}.md"
            
            if memory_file.exists():
                with open(memory_file) as f:
                    content = f.read()
                
                # Extract user requests (simple heuristic)
                lines = content.split('\n')
                for line in lines:
                    if line.strip().startswith('user') or line.startswith('Heath:'):
                        template = self._extract_template(line)
                        if len(template) > 10:  # Skip too-short templates
                            patterns[template] += 1
        
        return patterns
    
    def find_patterns(self, min_frequency=3):
        """Find patterns that appear frequently."""
        patterns = self.scan_sessions()
        return {p: c for p, c in patterns.items() if c >= min_frequency}
    
    def create_shortcut(self, template, name, response_template):
        """Create a new shortcut from a pattern."""
        shortcut = {
            "name": name,
            "template": template,
            "response": response_template,
            "created": datetime.now().isoformat(),
            "usage_count": 0
        }
        self.shortcuts["shortcuts"].append(shortcut)
        self._save_shortcuts()
        return shortcut
    
    def match_shortcut(self, text):
        """Check if text matches any shortcut."""
        template = self._extract_template(text)
        for shortcut in self.shortcuts.get("shortcuts", []):
            if shortcut["template"] == template:
                shortcut["usage_count"] += 1
                self._save_shortcuts()
                return shortcut
        return None
    
    def list_shortcuts(self):
        """List all available shortcuts."""
        return self.shortcuts.get("shortcuts", [])


if __name__ == "__main__":
    chunker = PatternChunker()
    
    # Find patterns
    print("Scanning for patterns...")
    patterns = chunker.find_patterns(min_frequency=2)
    print(f"Found {len(patterns)} patterns:")
    for p, c in sorted(patterns.items(), key=lambda x: -x[1])[:5]:
        print(f"  {c}x: {p[:60]}...")
    
    # List shortcuts
    shortcuts = chunker.list_shortcuts()
    print(f"\n{len(shortcuts)} shortcuts available")
