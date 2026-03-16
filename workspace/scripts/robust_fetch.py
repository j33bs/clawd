#!/usr/bin/env python3
"""
Robust Web Fetcher - Graceful degradation across multiple strategies.

Strategies:
1. requests with rotating user-agents
2. curl with fallback headers
3. wget fallback
4. Try alternative URLs (PDF, text versions)
"""
import subprocess
import requests
import urllib.parse
from pathlib import Path
from typing import Optional

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

HEADERS_BASE = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


def fetch_url(
    url: str,
    timeout: int = 15,
    max_retries: int = 3,
    user_agent_index: Optional[int] = None
) -> Optional[str]:
    """Fetch URL with graceful fallback chain."""
    
    # Primary strategies first
    for attempt in range(max_retries):
        ua = USER_AGENTS[(user_agent_index or 0) + attempt] if user_agent_index else USER_AGENTS[attempt % len(USER_AGENTS)]
        headers = {**HEADERS_BASE, "User-Agent": ua}
        
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 403:
                # Forbidden - skip to jina fallback
                break
            elif resp.status_code == 404:
                alt = _try_alternative_urls(url)
                if alt:
                    return alt
        except requests.RequestException:
            continue
    
    # Fallback: jina.ai extractor (bypasses most blocks)
    # Use curl subprocess - Python requests has issues with this URL format
    try:
        result = subprocess.run(
            ["curl", "-fsSL", "-L", "--max-time", str(timeout), 
             f"https://r.jina.ai/http://{url.replace('https://', '')}"],
            capture_output=True,
            text=True,
            timeout=timeout + 5
        )
        if result.returncode == 0 and result.stdout and "ParamValidationError" not in result.stdout and len(result.stdout) > 50:
            return result.stdout
    except Exception:
        pass
    try:
        resp = requests.get(jina_url, timeout=timeout)
        if resp.status_code == 200 and len(resp.text) > 100:
            return resp.text
    except Exception:
        pass
    
    return None
    
    # Strategy 1: requests with rotating UA
    for attempt in range(max_retries):
        ua = USER_AGENTS[(user_agent_index or 0) + attempt] if user_agent_index else USER_AGENTS[attempt % len(USER_AGENTS)]
        headers = {**HEADERS_BASE, "User-Agent": ua}
        
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 403:
                # Forbidden - try different UA
                continue
            elif resp.status_code == 404:
                # Try alternative URLs before giving up
                alt = _try_alternative_urls(url)
                if alt:
                    return alt
        except requests.RequestException:
            continue
    
    # Strategy 2: curl with headers
    for ua in USER_AGENTS[:2]:
        try:
            result = subprocess.run(
                ["curl", "-fsSL", "-A", ua, "-L", "--max-time", str(timeout), url],
                capture_output=True,
                text=True,
                timeout=timeout + 5
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except Exception:
            continue
    
    # Strategy 3: Try alternative URLs
    alt = _try_alternative_urls(url)
    if alt:
        return alt
    
    return None


def _try_alternative_urls(url: str) -> Optional[str]:
    """Try alternative URL variations."""
    parsed = urllib.parse.urlparse(url)
    
    alternatives = []
    
    # Try PDF version
    if ".pdf" not in url.lower():
        alternatives.append(url.rstrip("/") + ".pdf")
        alternatives.append(url.rstrip("/") + "/download")
    
    # Try without trailing slash
    if url.endswith("/"):
        alternatives.append(url.rstrip("/"))
    
    # Try textise dot iitty
    if "preprints.org" in url:
        # Try different paths
        alternatives.append(url.replace("manuscript", "article"))
        alternatives.append(url.replace("manuscript", "fulltext"))
    
    for alt_url in alternatives:
        for ua in USER_AGENTS[:2]:
            try:
                resp = requests.get(alt_url, headers={**HEADERS_BASE, "User-Agent": ua}, timeout=10)
                if resp.status_code == 200 and len(resp.text) > 100:
                    return resp.text
            except Exception:
                continue
    
    return None


def fetch_binary(url: str, output_path: Path) -> bool:
    """Fetch binary content (PDF, etc)."""
    for ua in USER_AGENTS[:2]:
        try:
            resp = requests.get(url, headers={"User-Agent": ua}, timeout=30, stream=True)
            if resp.status_code == 200:
                output_path.write_bytes(resp.content)
                return True
        except Exception:
            continue
    return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: robust_fetch.py <url>")
        sys.exit(1)
    
    result = fetch_url(sys.argv[1])
    if result:
        print(result[:2000])
    else:
        print("Failed to fetch")
