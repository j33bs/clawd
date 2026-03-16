#!/usr/bin/env python3
"""
Arxiv Skill Miner - Extract agent skills from arxiv papers
Based on: arxiv:2603.11808 framework for S=(C,π,T,R) extraction
Integrates with: tacti_skill_evolution for self-improving skills
"""
import subprocess
import json
import re
import sys
from pathlib import Path
from typing import Optional

# Add scripts to path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "workspace" / "memory"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

PAPERS_DIR = REPO_ROOT / "workspace" / "papers"
SKILLS_DIR = REPO_ROOT / "skills"


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


def register_with_evolution(skill_name: str, task: str, success: bool, error: str = None):
    """Register skill execution with the evolution system."""
    try:
        from tacti_skill_evolution import SkillExecution, get_evolution
        execution = SkillExecution(
            skill_name=skill_name,
            task=task,
            success=success,
            error=error,
            tool_failures=[]
        )
        evo = get_evolution()
        status = evo.observe(execution)
        
        # Auto-amend if threshold reached
        if evo.skills_state["skills"].get(skill_name, {}).get("failure_count", 0) >= 3:
            amendment = evo.amend(skill_name, auto_approve=False)
            if amendment:
                print(f"\n⚠️ Amendment proposed for {skill_name}: {amendment.rationale}")
        
        return status
    except Exception as e:
        print(f"Evolution integration error: {e}")
        return None


def create_skill_directory(skill_name: str, md_content: str) -> Path:
    """Create skill directory and SKILL.md file."""
    skill_dir = SKILLS_DIR / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(md_content)
    
    return skill_file


def mine_and_register(arxiv_id: str, skill_name: str = None) -> dict:
    """Full pipeline: mine skill + register with evolution + create skill file."""
    
    # Default skill name from paper ID
    if not skill_name:
        skill_name = f"arxiv_{arxiv_id}"
    
    print(f"Mining {arxiv_id} as '{skill_name}'...")
    
    # Fetch paper
    if not fetch_paper(arxiv_id):
        register_with_evolution(skill_name, f"fetch_{arxiv_id}", False, error="download_failed")
        return {"error": "Failed to fetch paper"}
    
    # Find tex - could be in subfolder or directly in papers dir
    tex_files = list(PAPERS_DIR.glob("*/article.tex")) + list(PAPERS_DIR.glob("article.tex"))
    if not tex_files:
        register_with_evolution(skill_name, f"parse_{arxiv_id}", False, error="no_tex_found")
        return {"error": "No article.tex found"}
    
    content = tex_files[0].read_text()
    
    # Extract skill tuple
    skill_tuple = extract_skill_tuple(content)
    
    # Generate SKILL.md
    md = generate_skill_md(arxiv_id, skill_tuple)
    
    # Create skill file
    skill_file = create_skill_directory(skill_name, md)
    
    # Register with evolution (success)
    register_with_evolution(skill_name, f"create_{arxiv_id}", True)
    
    return {
        "skill_name": skill_name,
        "skill_file": str(skill_file),
        "skill_tuple": skill_tuple
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: arxiv_miner.py <arxiv_id> [skill_name]")
        print("  <arxiv_id>   : e.g., 2603.11808")
        print("  [skill_name] : optional custom skill name")
        sys.exit(1)
    
    arxiv_id = sys.argv[1]
    skill_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = mine_and_register(arxiv_id, skill_name)
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"\n✓ Skill created: {result['skill_name']}")
        print(f"  File: {result['skill_file']}")
        print(f"\nSkill tuple: {json.dumps(result['skill_tuple'], indent=2)}")
