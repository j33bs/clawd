#!/usr/bin/env python3
"""
Research Paper Ingestion
Downloads and indexes research papers for TACTI(C)-R framework

Usage:
    python3 research_ingest.py --topics-file workspace/research/TOPICS.md --out-dir reports/research [--dry-run]
    python3 research_ingest.py add --url <url> --topic <topic>
    python3 research_ingest.py add --text "<full text>" --topic <topic>
    python3 research_ingest.py list --topic <topic>
    python3 research_ingest.py search "<query>"
"""
import argparse
import hashlib
import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen
import xml.etree.ElementTree as ET

try:
    from gap_analyzer import analyze_gaps, publish_gap_report
except Exception:  # pragma: no cover
    analyze_gaps = None
    publish_gap_report = None

DATA_DIR = Path(__file__).parent / "data"
PAPERS_FILE = DATA_DIR / "papers.jsonl"
ARXIV_API = "https://export.arxiv.org/api/query"
DATA_DIR.mkdir(exist_ok=True)

if not PAPERS_FILE.exists():
    PAPERS_FILE.touch()


def _run_gap_bridge(*, topics_file: Path) -> dict:
    if not callable(analyze_gaps) or not callable(publish_gap_report):
        return {"ok": False, "reason": "gap_analyzer_unavailable"}
    repo_root = Path(__file__).resolve().parents[2]
    report = analyze_gaps(
        papers_path=PAPERS_FILE,
        topics_file=topics_file,
        low_coverage_threshold=1,
        top_k=5,
    )
    publish = publish_gap_report(report=report, repo_root=repo_root)
    return {"ok": True, "report": report, "publish": publish}


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

    gap_topics = Path(__file__).parent / "TOPICS.md"
    try:
        bridge = _run_gap_bridge(topics_file=gap_topics)
        if bridge.get("ok"):
            publish = bridge.get("publish", {})
            print(f"   Gap report bridge: {publish.get('reason', 'ok')} -> {publish.get('path', '')}")
    except Exception as e:
        print(f"   Note: Gap analyzer bridge skipped: {e}")
    
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


def normalize_topic(raw: str) -> str:
    topic = raw.strip().lower().replace("-", "_").replace(" ", "_")
    topic = re.sub(r"[^a-z0-9_]+", "", topic)
    topic = re.sub(r"_+", "_", topic).strip("_")
    return topic


def parse_topics_file(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"topics file not found: {path}")

    topics: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue

        table_match = re.match(r"^\|\s*\*\*(?P<topic>[^*|]+)\*\*\s*\|", line)
        if table_match:
            normalized = normalize_topic(table_match.group("topic"))
            if normalized and normalized not in seen:
                seen.add(normalized)
                topics.append(normalized)
            continue

        heading_match = re.match(r"^####\s+(?P<topic>[A-Za-z0-9 _-]+)$", line)
        if heading_match:
            normalized = normalize_topic(heading_match.group("topic"))
            if normalized and normalized not in seen:
                seen.add(normalized)
                topics.append(normalized)

    return topics


def arxiv_query(topic: str, max_results: int) -> str:
    query = topic.replace("_", " ")
    params = urlencode(
        {
            "search_query": f'all:"{query}"',
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    return f"{ARXIV_API}?{params}"


def probe_arxiv_connectivity(timeout: int = 10) -> dict:
    url = arxiv_query("artificial intelligence", 1)
    try:
        with urlopen(url, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            return {"ok": True, "status": status, "url": url}
    except (URLError, HTTPError, TimeoutError) as err:
        return {"ok": False, "error": str(err), "url": url}


def fetch_arxiv_entries(topic: str, max_results: int = 1, timeout: int = 20) -> list[dict]:
    url = arxiv_query(topic, max_results)
    with urlopen(url, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    root = ET.fromstring(raw)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries: list[dict] = []
    for entry in root.findall("atom:entry", ns):
        entry_id = entry.findtext("atom:id", default="", namespaces=ns).strip()
        title = " ".join(entry.findtext("atom:title", default="", namespaces=ns).split())
        summary = " ".join(entry.findtext("atom:summary", default="", namespaces=ns).split())
        updated = entry.findtext("atom:updated", default="", namespaces=ns).strip()
        if not title or not summary:
            continue
        entries.append(
            {
                "entry_id": entry_id,
                "title": title,
                "summary": summary,
                "updated": updated,
                "url": entry_id,
            }
        )
    return entries


def ingest_topics(topics_file: Path, out_dir: Path, dry_run: bool = False, max_results: int = 1) -> tuple[int, dict]:
    topics = parse_topics_file(topics_file)
    connectivity = probe_arxiv_connectivity()
    out_dir.mkdir(parents=True, exist_ok=True)

    existing_ids: set[str] = set()
    with open(PAPERS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            paper_id = record.get("id")
            if isinstance(paper_id, str):
                existing_ids.add(paper_id)

    docs_ingested = 0
    fetch_errors: list[str] = []
    fetched_by_topic: dict[str, int] = {}

    if connectivity.get("ok") and not dry_run:
        for topic in topics:
            try:
                entries = fetch_arxiv_entries(topic, max_results=max_results)
            except Exception as err:  # pragma: no cover - defensive
                fetch_errors.append(f"{topic}: {err}")
                continue

            fetched_by_topic[topic] = len(entries)
            for entry in entries:
                content = f"{entry['title']}\n\n{entry['summary']}"
                paper_id = compute_hash(f"{entry['entry_id']}::{content[:1000]}")
                if paper_id in existing_ids:
                    continue
                record = {
                    "id": paper_id,
                    "title": entry["title"],
                    "topic": topic,
                    "source": "arxiv",
                    "url": entry["url"],
                    "content": content[:50000],
                    "length": len(content),
                    "added_at": datetime.now(timezone.utc).isoformat(),
                    "tacti_relevance": 0.6,
                    "metadata": {
                        "entry_updated": entry["updated"],
                    },
                }
                with open(PAPERS_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                existing_ids.add(paper_id)
                docs_ingested += 1

    status = {
        "topics_file": str(topics_file),
        "topics_count": len(topics),
        "topics": topics,
        "docs_ingested": docs_ingested,
        "fetched_by_topic": fetched_by_topic,
        "dry_run": dry_run,
        "connectivity": connectivity,
        "errors": fetch_errors,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    status_path = out_dir / "ingest_status.json"
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not connectivity.get("ok"):
        return 1, status
    if fetch_errors:
        return 1, status
    return 0, status


def cmd_ingest_topics(args: argparse.Namespace) -> int:
    topics_file = Path(args.topics_file).expanduser()
    out_dir = Path(args.out_dir).expanduser()
    code, status = ingest_topics(
        topics_file=topics_file,
        out_dir=out_dir,
        dry_run=bool(args.dry_run),
        max_results=max(1, int(args.max_results_per_topic)),
    )
    try:
        bridge = _run_gap_bridge(topics_file=topics_file)
        status["gap_report"] = bridge
    except Exception as err:
        status["gap_report"] = {"ok": False, "reason": f"bridge_error:{err}"}
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research Paper Ingestion for TACTI(C)-R")
    parser.add_argument("--topics-file", help="Ingest mode: markdown topic file")
    parser.add_argument("--out-dir", default="reports/research", help="Ingest status output directory")
    parser.add_argument("--dry-run", action="store_true", help="Ingest mode: enumerate topics + connectivity only")
    parser.add_argument("--max-results-per-topic", type=int, default=1, help="Ingest mode: arXiv entries per topic")

    sub = parser.add_subparsers(dest="cmd", required=False)
    
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
    if args.topics_file:
        return cmd_ingest_topics(args)
    if hasattr(args, "func"):
        return args.func(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
