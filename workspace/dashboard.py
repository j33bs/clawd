#!/usr/bin/env python3
"""
System Dashboard
Generates a simple HTML dashboard of TACTI system health.
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "memory"))
sys.path.insert(0, str(Path(__file__).parent / "research"))

from tacti_core import get_core
from conversation_summarizer import ConversationSummarizer
from insight_tracker import InsightTracker

def generate_dashboard():
    """Generate HTML dashboard."""
    core = get_core()
    summarizer = ConversationSummarizer()
    tracker = InsightTracker()
    
    # Get data
    rel = core.get_relationship_health()
    ar = core.get_arousal_state()
    summary = summarizer.generate_summary()
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>TACTI System Dashboard</title>
    <style>
        body {{ font-family: -apple-system, system-ui, sans-serif; padding: 20px; background: #1a1a2e; color: #eee; }}
        .card {{ background: #16213e; border-radius: 12px; padding: 20px; margin: 10px; display: inline-block; width: 300px; }}
        .title {{ font-size: 14px; color: #888; text-transform: uppercase; }}
        .value {{ font-size: 32px; font-weight: bold; margin: 10px 0; }}
        .good {{ color: #4ade80; }}
        .warn {{ color: #facc15; }}
        .bad {{ color: #f87171; }}
        h1 {{ color: #fff; }}
    </style>
</head>
<body>
    <h1>🧠 TACTI System Dashboard</h1>
    <p>Last updated: {datetime.now().strftime('%H:%M:%S')}</p>
    
    <div class="card">
        <div class="title">Relationship</div>
        <div class="value {'good' if rel['trust'] > 0.8 else 'warn'}">{rel['trust']:.0%}</div>
        <div>Trust Score</div>
        <div>Attunement: {rel['attunement']:.0%}</div>
    </div>
    
    <div class="card">
        <div class="title">Arousal State</div>
        <div class="value">{ar['state'].upper()}</div>
        <div>Avg tokens/msg: {ar['metrics']['avg_tokens_per_message']:.0f}</div>
    </div>
    
    <div class="card">
        <div class="title">Topics</div>
        <div class="value">{len(summary['top_topics'])}</div>
        <div>Top: {', '.join(summary['top_topics'][:3])}</div>
    </div>
    
    <div class="card">
        <div class="title">Insights</div>
        <div class="value">{len(tracker.get_all())}</div>
        <div>Tags: {len(tracker.insights['tags'])}</div>
    </div>
</body>
</html>
"""
    
    return html


if __name__ == "__main__":
    print(generate_dashboard())
