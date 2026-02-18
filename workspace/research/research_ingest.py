#!/usr/bin/env python3
"""
Research Paper Ingestion
Downloads and indexes research papers for TACTI(C)-R framework

Usage:
    python3 research_ingest.py add --url <url> --topic <topic>
    python3 research_ingest.py add --text "<full text>" --topic <topic>
    python3 research_ingest.py list --topic <topic>
    python3 research_ingest.py search "<query>"
"""
import argparse
import hashlib
import json
import os
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Try to import readability for web scraping
try:
    from urllib.request import urlopen
    from html import unescape
    HAVE_READABILITY = False  # Keep simple for now
except ImportError:
    HAVE_READABILITY = False

DATA_DIR = Path(__file__).parent / "data"
PAPERS_FILE = DATA_DIR / "papers.jsonl"
DATA_DIR.mkdir(exist_ok=True)

if not PAPERS_FILE.exists():
    PAPERS_FILE.touch()


def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:12]


def fetch_url(url: str) -> str:
    """Fetch and extract text from URL."""
    try:
        import subprocess
        # Try using web_fetch if available, otherwise curl
        result = subprocess.run(
            ["curl", "-sS", url],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return result.stdout
    except Exception as e:
        return f"Error fetching: {e}"
    return ""


def extract_text_from_html(html: str) -> str:
    """Simple HTML to text extraction."""
    # Remove scripts and styles
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Replace br/p with newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    
    # Remove all tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode HTML entities
    import html
    text = html.unescape(text)
    
    # Clean whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    return text


def cmd_add(args: argparse.Namespace) -> int:
    """Add a research paper."""
    topic = args.topic or "general"
    source = args.url or "manual"
    
    # Get content
    if args.text:
        content = args.text
    elif args.url:
        print(f"Fetching {args.url}...")
        html = fetch_url(args.url)
        content = extract_text_from_html(html)
        
        if len(content) < 100:
            print(f"Warning: Only got {len(content)} chars. URL may not be accessible.")
            content = input("Paste full text instead: ")
    else:
        print("Error: Must provide --url or --text")
        return 1
    
    if len(content) < 100:
        print("Error: Content too short")
        return 1
    
    # Compute hash
    paper_id = compute_hash(content[:1000])
    
    # Extract title (first line or first 100 chars)
    lines = content.split('\n')
    title = lines[0].strip()[:100] if lines else "Untitled"
    if len(title) < 5 and len(lines) > 1:
        title = lines[1].strip()[:100]
    
    # Build paper record
    paper = {
        "id": paper_id,
        "title": title,
        "topic": topic,
        "source": source,
        "url": args.url,
        "content": content[:50000],  # Limit to 50k chars
        "length": len(content),
        "added_at": datetime.now(timezone.utc).isoformat(),
        "tacti_relevance": args.relevance or 0.5
    }
    
    # Save
    with open(PAPERS_FILE, "a") as f:
        f.write(json.dumps(paper, ensure_ascii=False) + "\n")
    
    print(f"✅ Added paper: {title}")
    print(f"   ID: {paper_id}")
    print(f"   Topic: {topic}")
    print(f"   Length: {len(content)} chars")
    print(f"   TACTI(C)-R Relevance: {paper['tacti_relevance']}")
    
    # Also add to knowledge graph
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from knowledge_base.graph.store import KnowledgeGraphStore
        
        kb = KnowledgeGraphStore(Path(__file__).parent / "knowledge_base" / "data")
        kb.add_entity(
            name=title[:50],
            entity_type="research_paper",
            content=f"TACTI(C)-R research paper: {title}",
            source="research_ingest",
            metadata={"topic": topic, "paper_id": paper_id, "url": args.url}
        )
        print(f"   Indexed in Knowledge Graph")
    except Exception as e:
        print(f"   Note: Could not index to KB: {e}")
    
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List papers."""
    papers = []
    with open(PAPERS_FILE) as f:
        for line in f:
            if line.strip():
                papers.append(json.loads(line))
    
    if not papers:
        print("No papers stored yet.")
        return 0
    
    # Filter by topic
    if args.topic:
        papers = [p for p in papers if p.get("topic") == args.topic]
    
    print(f"\n📚 Research Papers ({len(papers)} total)")
    print("=" * 60)
    
    for p in papers:
        relevance = p.get("tacti_relevance", 0.5)
        stars = "★" * int(relevance * 5)
        print(f"\n{p['title'][:50]}...")
        print(f"   Topic: {p.get('topic', 'general')} | {stars}")
        if p.get('url'):
            print(f"   URL: {p['url'][:60]}...")
        print(f"   Added: {p['added_at'][:10]}")
    
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search papers."""
    query = args.query.lower()
    
    papers = []
    with open(PAPERS_FILE) as f:
        for line in f:
            if line.strip():
                papers.append(json.loads(line))
    
    results = []
    for p in papers:
        score = 0
        if query in p.get('title', '').lower():
            score += 10
        if query in p.get('content', '').lower():
            score += 5
        if query in p.get('topic', '').lower():
            score += 3
        
        if score > 0:
            results.append((score, p))
    
    results.sort(key=lambda x: x[0], reverse=True)
    
    print(f"\n🔍 Search: \"{query}\" ({len(results)} results)")
    print("=" * 60)
    
    for score, p in results[:10]:
        print(f"\n[{score}] {p['title'][:60]}")
        # Show snippet
        content = p.get('content', '')
        idx = content.lower().find(query)
        if idx >= 0:
            snippet = content[max(0, idx-30):idx+50]
            print(f"   ...{snippet}...")
    
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research Paper Ingestion for TACTI(C)-R")
    sub = parser.add_subparsers(dest="cmd", required=True)
    
    # add
    a = sub.add_parser("add", help="Add a research paper")
    a.add_argument("--url", help="URL to fetch")
    a.add_argument("--text", help="Full text content")
    a.add_argument("--topic", help="Topic/category")
    a.add_argument("--relevance", type=float, default=0.5, help="TACTI(C)-R relevance 0-1")
    a.set_defaults(func=cmd_add)
    
    # list
    l = sub.add_parser("list", help="List papers")
    l.add_argument("--topic", help="Filter by topic")
    l.set_defaults(func=cmd_list)
    
    # search
    s = sub.add_parser("search", help="Search papers")
    s.add_argument("query", help="Search query")
    s.set_defaults(func=cmd_search)
    
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
