#!/usr/bin/env python3
"""
Knowledge Base - Main CLI
Unified interface for QMD + HiveMind + Knowledge Graph
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Add current dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from graph.store import KnowledgeGraphStore
from graph.entities import extract_entities
from agentic.intent import classify_intent
from agentic.retrieve import multi_step_retrieve
from agentic.synthesize import synthesize_response

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def cmd_query(args: argparse.Namespace) -> int:
    """Agentic RAG query - the main entry point."""
    query = args.query
    
    # Step 1: Classify intent
    intent = classify_intent(query)
    print(f"🔍 Intent: {intent['strategy']}")
    
    # Step 2: Multi-step retrieval
    results = multi_step_retrieve(query, intent, args.agent)
    
    # Step 3: Synthesize response
    response = synthesize_response(query, results, intent)
    
    print("\n" + "=" * 50)
    print("📚 ANSWER")
    print("=" * 50)
    print(response["answer"])
    
    if response.get("citations"):
        print("\n📋 CITATIONS")
        for cit in response["citations"]:
            print(f"  - {cit}")
    
    if response.get("sources"):
        print("\n🔗 SOURCES")
        for src in response["sources"]:
            print(f"  - {src}")
    
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    """Add content to knowledge base."""
    content = args.content
    kind = args.type or "fact"
    
    # Extract entities
    entities = extract_entities(content)
    
    # Store in graph
    store = KnowledgeGraphStore(DATA_DIR)
    unit_id = store.add_entity(
        name=content[:50],
        entity_type=kind,
        content=content,
        source=args.source or "manual",
        metadata={"entities": entities}
    )
    
    print(f"✅ Added {kind}: {content[:50]}...")
    print(f"   Entity ID: {unit_id}")
    print(f"   Extracted: {entities}")
    
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    """Query knowledge graph."""
    store = KnowledgeGraphStore(DATA_DIR)
    
    if args.entity:
        # Show specific entity
        results = store.get_entity(args.entity)
        if results:
            for r in results:
                print(f"\n📦 {r['name']} ({r['entity_type']})")
                print(f"   {r['content']}")
                if r.get('relations'):
                    print(f"   Relations: {r['relations']}")
        else:
            print(f"No entity found: {args.entity}")
    else:
        # Show all
        results = store.all_entities(limit=args.limit or 20)
        print(f"📊 Knowledge Graph ({len(results)} entities)")
        for r in results:
            print(f"  • {r['name'][:40]}... [{r['entity_type']}]")
    
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Show knowledge base stats."""
    store = KnowledgeGraphStore(DATA_DIR)
    
    # Graph stats
    graph_stats = store.stats()
    
    # QMD stats (via exec)
    import subprocess
    try:
        result = subprocess.run(
            ["npx", "@tobilu/qmd", "status"],
            capture_output=True,
            text=True,
            timeout=10
        )
        qmd_status = result.stdout
    except Exception:
        qmd_status = "QMD not available"
    
    print("=" * 40)
    print("📈 KNOWLEDGE BASE STATS")
    print("=" * 40)
    print(f"\n🕸️  Knowledge Graph:")
    print(f"   Entities: {graph_stats.get('total', 0)}")
    print(f"   Relations: {graph_stats.get('relations', 0)}")
    
    print(f"\n🔍 QMD Search:")
    for line in qmd_status.split('\n')[:10]:
        if line.strip():
            print(f"   {line}")
    
    # HiveMind stats
    hive_path = Path(__file__).parents[1] / "hivemind" / "data" / "knowledge_units.jsonl"
    if hive_path.exists():
        with open(hive_path) as f:
            hive_count = sum(1 for _ in f)
        print(f"\n🧠 HiveMind:")
        print(f"   Knowledge Units: {hive_count}")
    
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Sync recent changes to knowledge base."""
    # Extract entities from recent QMD-indexed docs
    import subprocess
    
    # Get recent files
    try:
        result = subprocess.run(
            ["npx", "@tobilu/qmd", "ls", "-n", "20"],
            capture_output=True,
            text=True,
            timeout=15
        )
        files = [l.strip() for l in result.stdout.split('\n') if l.strip() and not l.startswith('qmd://')]
    except Exception as e:
        print(f"❌ QMD not available: {e}")
        return 1
    
    store = KnowledgeGraphStore(DATA_DIR)
    count = 0
    
    for f in files[:10]:  # Limit to 10 for now
        if f.endswith('.md'):
            # Extract and store entities
            entities = extract_entities(f"Document: {f}")
            if entities:
                store.add_entity(
                    name=f[:50],
                    entity_type="document",
                    content=f,
                    source="qmd-sync",
                    metadata={"entities": entities}
                )
                count += 1
    
    print(f"✅ Synced {count} documents to knowledge graph")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Knowledge Base CLI - Unified search + memory + graph"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    
    # query
    q = sub.add_parser("query", help="Ask a question (Agentic RAG)")
    q.add_argument("query", help="Question to answer")
    q.add_argument("--agent", default="main", help="Agent scope")
    q.set_defaults(func=cmd_query)
    
    # add
    a = sub.add_parser("add", help="Add content to KB")
    a.add_argument("--content", required=True, help="Content to add")
    a.add_argument("--type", choices=["fact", "decision", "lesson", "procedure"], help="Type of knowledge")
    a.add_argument("--source", help="Source of the knowledge")
    a.set_defaults(func=cmd_add)
    
    # graph
    g = sub.add_parser("graph", help="Query knowledge graph")
    g.add_argument("--entity", help="Specific entity to look up")
    g.add_argument("--limit", type=int, default=20, help="Limit results")
    g.set_defaults(func=cmd_graph)
    
    # stats
    s = sub.add_parser("stats", help="Show KB statistics")
    s.set_defaults(func=cmd_stats)
    
    # sync
    y = sub.add_parser("sync", help="Sync recent documents to KB")
    y.set_defaults(func=cmd_sync)
    
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
