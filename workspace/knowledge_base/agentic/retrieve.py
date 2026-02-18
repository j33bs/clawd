"""
Multi-Step Retrieval
Coordinates QMD, HiveMind, and Knowledge Graph for retrieval
"""
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Any

# Import local modules
from .intent import extract_entities_from_query, build_search_query


def run_qmd_search(query: str, limit: int = 5) -> List[Dict]:
    """Run QMD search query."""
    results = []
    try:
        result = subprocess.run(
            ["npx", "@tobilu/qmd", "search", query, "-n", str(limit), "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path(__file__).parents[2].parent.parent)
        )
        
        if result.returncode != 0:
            return []
        
        # Parse JSON output (QMD returns array)
        try:
            data = json.loads(result.stdout)
            if isinstance(data, list):
                for item in data:
                    results.append({
                        "source": "qmd",
                        "type": "document",
                        "title": item.get("title", ""),
                        "path": item.get("file", ""),
                        "score": item.get("score", 0),
                        "content": item.get("snippet", "")[:500]
                    })
        except json.JSONDecodeError:
            # Fallback: parse line by line
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    try:
                        data = json.loads(line)
                        results.append({
                            "source": "qmd",
                            "type": "document",
                            "title": data.get("title", ""),
                            "path": data.get("path", ""),
                            "score": data.get("score", 0),
                            "content": data.get("content", "")[:500]
                        })
                    except json.JSONDecodeError:
                        continue
        
        return results
    
    except Exception as e:
        return [{"source": "qmd", "error": str(e)}]


def run_qmd_vsearch(query: str, limit: int = 5) -> List[Dict]:
    """Run QMD vector semantic search."""
    try:
        result = subprocess.run(
            ["npx", "@tobilu/qmd", "vsearch", query, "-n", str(limit)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).parents[2].parent.parent)
        )
        
        if result.returncode != 0:
            return []
        
        # Similar parsing to search
        return parse_qmd_output(result.stdout)
    
    except Exception as e:
        return [{"source": "qmd_vsearch", "error": str(e)}]


def run_hivemind_query(query: str, agent: str = "main", limit: int = 5) -> List[Dict]:
    """Run HiveMind query."""
    try:
        result = subprocess.run(
            ["python3", "scripts/memory_tool.py", "query", 
             "--agent", agent, "--q", query, "--limit", str(limit), "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(Path(__file__).parents[2].parent.parent)
        )
        
        if result.returncode != 0:
            return []
        
        data = json.loads(result.stdout)
        
        results = []
        for r in data.get("results", []):
            results.append({
                "source": "hivemind",
                "type": r.get("kind", "fact"),
                "scope": r.get("agent_scope", "shared"),
                "content": r.get("content", "")[:500],
                "metadata": r.get("metadata", {})
            })
        
        return results
    
    except Exception as e:
        return [{"source": "hivemind", "error": str(e)}]


def run_graph_search(query: str, limit: int = 5) -> List[Dict]:
    """Search knowledge graph."""
    try:
        kb_dir = Path(__file__).parent.parent
        result = subprocess.run(
            ["python3", "workspace/knowledge-base/kb.py", "graph", "--limit", str(limit)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(Path(__file__).parents[2].parent.parent)
        )
        
        if result.returncode != 0:
            return []
        
        return [{
            "source": "graph",
            "type": "entity",
            "content": result.stdout[:500]
        }]
    
    except Exception as e:
        return [{"source": "graph", "error": str(e)}]


def multi_step_retrieve(query: str, intent: Dict, agent: str = "main") -> Dict:
    """
    Execute multi-step retrieval based on intent.
    
    Returns:
        {
            "qmd": [...],
            "hivemind": [...],
            "graph": [...],
            "combined": [...]
        }
    """
    # Build optimized search query
    search_query = build_search_query(query)
    
    # Extract entities
    entities = extract_entities_from_query(query)
    
    results = {
        "query": query,
        "intent": intent,
        "entities": entities,
        "qmd": [],
        "hivemind": [],
        "graph": [],
        "combined": []
    }
    
    steps = intent.get("steps", ["qmd_search"])
    
    # Execute steps
    for step in steps:
        if step == "qmd_search" and "qmd" not in str(results["qmd"]):
            results["qmd"] = run_qmd_search(search_query, limit=5)
        
        elif step == "qmd_vsearch":
            v_results = run_qmd_vsearch(search_query, limit=5)
            results["qmd"].extend(v_results)
        
        elif step == "hivemind_query" and not results["hivemind"]:
            results["hivemind"] = run_hivemind_query(query, agent, limit=5)
        
        elif step == "graph_search" and not results["graph"]:
            results["graph"] = run_graph_search(query, limit=5)
        
        elif step == "fallback":
            # Try QMD if nothing else worked
            if not results["qmd"]:
                results["qmd"] = run_qmd_search(query, limit=3)
    
    # Combine results (prioritize by source)
    combined = []
    
    # Add QMD results
    for r in results["qmd"]:
        r["priority"] = 1
        combined.append(r)
    
    # Add HiveMind results
    for r in results["hivemind"]:
        r["priority"] = 2
        combined.append(r)
    
    # Add Graph results
    for r in results["graph"]:
        r["priority"] = 3
        combined.append(r)
    
    # Sort by priority
    combined.sort(key=lambda x: x.get("priority", 99))
    results["combined"] = combined
    
    return results


def parse_qmd_output(output: str) -> List[Dict]:
    """Parse QMD command output."""
    results = []
    
    for line in output.strip().split('\n'):
        if line.strip() and not line.startswith('qmd://'):
            results.append({
                "source": "qmd",
                "type": "document",
                "content": line[:500]
            })
    
    return results
