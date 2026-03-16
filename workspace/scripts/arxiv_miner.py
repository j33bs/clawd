#!/usr/bin/env python3
"""
Arxiv Skill Miner - Extract agent skills from arxiv papers
Based on: arxiv:2603.11808 framework for S=(C,π,T,R) extraction
"""
import subprocess
import json
import re
import sys
from pathlib import Path
from typing import Optional

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

PAPERS_DIR = Path(__file__).parent.parent / "papers"


def fetch_paper(arxiv_id: str) -> Optional[Path]:
    """Download arxiv paper source (tar.gz)."""
    url = f"https://arxiv.org/e-print/{arxiv_id}"
    output = PAPERS_DIR / f"{arxiv_id}.tar.gz"
    
    result = subprocess.run(
        ["curl", "-fsSL", "-o", str(output), "--max-time", "60", url],
        capture_output=True
    )
    
    if result.returncode == 0 and output.exists():
        # Extract
        subprocess.run(["tar", "-xzf", str(output), "-C", str(PAPERS_DIR)], capture_output=True)
        return PAPERS_DIR
    return None


def extract_skill_tuple(tex_content: str) -> dict:
    """Extract S=(C,π,T,R) components from tex source."""
    
    # Extract applicability conditions (C)
    conditions = []
    for pattern in [r"applicable.*?when", r"prerequisite", r"requires?\s+(\w+)"]:
        matches = re.findall(pattern, tex_content, re.IGNORECASE)
        conditions.extend(matches)
    
    # Extract policy (π) - procedural steps
    policy = []
    for pattern in [r"step\s+\d+[:\.]\s*(.+?)(?=\n|step)", r"procedure[:\s]+(.+?)(?=\n\n)"]:
        matches = re.findall(pattern, tex_content, re.IGNORECASE | re.DOTALL)
        policy.extend([m.strip()[:200] for m in matches[:5]])
    
    # Extract trigger patterns (T)
    triggers = []
    for pattern in [r"triggered?\s+by", r"activate", r"invok"]:
        matches = re.findall(pattern, tex_content, re.IGNORECASE)
        triggers.extend(matches)
    
    # Extract resources (R)
    resources = []
    for pattern in [r"require[s]?\s+(\w+)", r"need[s]?\s+(\w+)", r"depend[s]?\s+on\s+(\w+)"]:
        matches = re.findall(pattern, tex_content, re.IGNORECASE)
        resources.extend(matches)
    
    return {
        "C": list(set(conditions))[:5],
        "π": policy[:5],
        "T": list(set(triggers))[:5],
        "R": list(set(resources))[:5]
    }


def generate_skill_md(paper_id: str, skill_tuple: dict) -> str:
    """Generate SKILL.md from extracted tuple."""
    
    md = f"""# Extracted Skill: {paper_id}

## Formal Structure
S = (C, π, T, R)

## Applicability Conditions (C)
"""
    for c in skill_tuple.get("C", []):
        md += f"- {c}\n"
    
    md += "\n## Policy (π)\n"
    for p in skill_tuple.get("π", []):
        md += f"- {p}\n"
    
    md += "\n## Triggers (T)\n"
    for t in skill_tuple.get("T", []):
        md += f"- {t}\n"
    
    md += "\n## Resources (R)\n"
    for r in skill_tuple.get("R", []):
        md += f"- {r}\n"
    
    return md


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: arxiv_miner.py <arxiv_id>")
        sys.exit(1)
    
    paper_id = sys.argv[1]
    print(f"Mining {paper_id}...")
    
    if fetch_paper(paper_id):
        # Find extracted tex
        tex_files = list(PAPERS_DIR.glob("*/article.tex"))
        if tex_files:
            content = tex_files[0].read_text()
            skill = extract_skill_tuple(content)
            print(json.dumps(skill, indent=2))
            
            # Generate skill md
            md = generate_skill_md(paper_id, skill)
            print("\n--- Generated SKILL.md ---\n")
            print(md)
        else:
            print("No article.tex found")
    else:
        print("Failed to fetch paper")
