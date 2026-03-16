#!/usr/bin/env python3
"""HMBEA CLI Entry Point"""
import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hmbea.graph import HMBEAGraph


def main():
    parser = argparse.ArgumentParser(description="HMBEA - Hierarchical Multi-Being Evolutionary Architecture")
    parser.add_argument("task", help="Task to execute")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--trace", action="store_true", help="Include trace in output")
    
    args = parser.parse_args()
    
    try:
        runtime = HMBEAGraph()
        result = runtime.run(args.task)
        
        output = {
            "answer": result.get("final_answer", ""),
            "escalated": result.get("escalate", False),
        }
        
        if args.trace:
            output["trace"] = result.get("trace", [])
        
        if args.json:
            print(json.dumps(output, indent=2))
        else:
            print(output["answer"])
            if output.get("escalated"):
                print("\n[Escalated to frontier model]")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
