"""
search_tool.py — Panda AI Search Engine V3
Fix: Google News RSS gives redirect URLs → extract real URLs first
Sources:
  1. Google News RSS  → feedparser + real URL extraction
  2. trafilatura      → full article body from real URLs
  3. Wikipedia API    → always works
"""

import feedparser
import requests
import trafilatura
import re
import random
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs

REQUEST_TIMEOUT = 10

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
]

def get_ua():
    return random.choice(USER_AGENTS)

def _now():
    n = datetime.now()
    return {
        "date":       n.strftime("%B %d, %Y"),
        "year":       str(n.year),
        "month_year": n.strftime("%B %Y"),
    }

def clean_text(text, limit=1000):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[|*©®\[\]{}\\]', ' ', text)
    noise = [
        r'accept\s+cookies?', r'privacy\s+policy', r'subscribe\s+now',
        r'sign\s+up', r'log\s+in', r'advertisement', r'sponsored',
        r'click\s+here', r'read\s+more', r'all\s+rights\s+reserved',
        r'copyright\s+\d{4}',
    ]
    for p in noise:
        text = re.sub(p, ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text[:limit]

def expand_query(query):
    q = query
    rules = [
        (r'\bpm\s+of\s+india\b',  'Prime Minister of India'),
        (r'\bpm\s+india\b',       'Prime Minister India'),
        (r'\bcurrent\s+pm\b',     'current Prime Minister India'),
        (r'\bwho\s+is\s+pm\b',    'who is Prime Minister of India'),
        (r'\bcm\s+of\s+(\w+)',    r'Chief Minister of \1'),
        (r'\bwho\s+is\s+cm\b',    'who is Chief Minister'),
        (r'\bcurrent\s+cm\b',     'current Chief Minister'),
        (r'\bipl\b',              'IPL Indian Premier League'),
    ]
    for pattern, replacement in rules:
        q = re.sub(pattern, replacement, q, flags=re.IGNORECASE)
    return q.strip()

# ── Resolve Google News redirect URL to real article URL ──
def resolve_google_news_url(url):
    """
    Google News RSS gives redirect URLs like:
    https://news.google.com/rss/articles/CBMi...
    
    We need to follow the redirect to get the real article URL.
    """
    try:
        if "news.google.com" not in url:
            return url  # already a real URL
        
        res = requests.get(
            url,
            headers={"User-Agent": get_ua()},
            timeout=8,
            allow_redirects=True,  # follow redirects
        )
        final_url = res.url
        
        # If still google URL, try to extract from query params
        if "google.com" in final_url:
            parsed = urlparse(final_url)
            params = parse_qs(parsed.query)
            if "url" in params:
                return params["url"][0]
            return ""
        
        print(f"  Resolved: {url[:50]} → {final_url[:60]}")
        return final_url
    except Exception as e:
        print(f"  Resolve error: {e}")
        return ""

# ── SOURCE 1: Google News RSS ──
def fetch_google_news_rss(query, max_items=6):
    results = []
    try:
        encoded = requests.utils.quote(query)
        url     = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        print(f"RSS: {url[:100]}")
        feed = feedparser.parse(url)
        if not feed.entries:
            print("RSS: 0 entries")
            return []
        for entry in feed.entries[:max_items]:
            title     = entry.get("title", "").strip()
            summary   = clean_text(entry.get("summary", ""), 500)
            # Try to get source URL from entry
            source_url = ""
            # feedparser sometimes gives real URL in 'source' or 'links'
            for link in entry.get("links", []):
                href = link.get("href", "")
                if href and "google.com" not in href:
                    source_url = href
                    break
            # fallback to entry link (Google redirect)
            if not source_url:
                source_url = entry.get("link", "")
            
            if not title:
                continue
            results.append({
                "title":     title,
                "summary":   summary or title,
                "url":       source_url,
                "published": entry.get("published", "")[:16],
                "source":    "Google News",
                "body":      "",
            })
        print(f"RSS: {len(results)} entries")
    except Exception as e:
        print(f"RSS error: {e}")
    return results

# ── SOURCE 2: trafilatura on real URLs ──
def _fetch_one_article(url):
    """Resolve Google redirect → fetch real page → trafilatura extract."""
    try:
        # Step 1: Resolve redirect if Google URL
        real_url = resolve_google_news_url(url) if "google.com" in url else url
        if not real_url:
            print(f"  Could not resolve URL: {url[:50]}")
            return url, ""

        # Step 2: Fetch real article
        res = requests.get(
            real_url,
            headers={
                "User-Agent": get_ua(),
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://www.google.com/",
            },
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        print(f"  Article HTTP {res.status_code}: {real_url[:60]}")

        if res.status_code != 200:
            return url, ""

        # Step 3: Extract with trafilatura
        text = trafilatura.extract(
            res.text,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_precision=False,
        )
        if text:
            cleaned = clean_text(text, 1000)
            print(f"  trafilatura: {len(cleaned)} chars ✅")
            return url, cleaned
        else:
            print(f"  trafilatura: 0 chars")
            return url, ""
    except Exception as e:
        print(f"  Article error ({url[:40]}): {e}")
        return url, ""

def enrich_articles(rss_results, max_workers=3):
    if not rss_results:
        return rss_results

    urls = [r["url"] for r in rss_results if r.get("url")]
    print(f"Fetching {len(urls)} articles...")

    body_map = {}
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(_fetch_one_article, u): u for u in urls}
            for fut in as_completed(futures, timeout=REQUEST_TIMEOUT + 5):
                try:
                    url, body = fut.result(timeout=2)
                    if body:
                        body_map[url] = body
                except Exception:
                    pass
    except Exception as e:
        print(f"Enrich error: {e}")

    enriched = 0
    for r in rss_results:
        r["body"] = body_map.get(r.get("url", ""), "")
        if r["body"]:
            enriched += 1

    print(f"Articles enriched: {enriched}/{len(rss_results)}")
    return rss_results

# ── SOURCE 3: Wikipedia ──
def _wiki_intro(title):
    try:
        res = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "prop": "extracts",
                "exintro": True, "explaintext": True,
                "titles": title, "format": "json", "redirects": 1,
            },
            headers={"User-Agent": "PandaAI/4.4"},
            timeout=REQUEST_TIMEOUT,
        )
        if res.status_code == 200:
            pages = res.json().get("query", {}).get("pages", {})
            for p in pages.values():
                return clean_text(p.get("extract", ""), 700)
    except Exception:
        pass
    return ""

def search_wikipedia(query):
    results = []
    try:
        clean_q = re.sub(
            r'\b(current|latest|today|who is|the|2026|2025|April|March|news)\b',
            '', query, flags=re.IGNORECASE
        ).strip()
        res = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search",
                "srsearch": clean_q, "format": "json",
                "srlimit": 3, "srprop": "snippet|timestamp",
            },
            headers={"User-Agent": "PandaAI/4.4"},
            timeout=REQUEST_TIMEOUT,
        )
        if res.status_code == 200:
            for item in res.json().get("query", {}).get("search", []):
                title   = item.get("title", "")
                snippet = clean_text(item.get("snippet", ""), 400)
                ts      = item.get("timestamp", "")[:10]
                intro   = _wiki_intro(title)
                content = intro if intro else snippet
                if title and content:
                    results.append({
                        "title":     f"Wikipedia: {title}",
                        "summary":   content,
                        "body":      "",
                        "url":       f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                        "published": ts,
                        "source":    "Wikipedia",
                    })
        print(f"Wikipedia: {len(results)} results")
    except Exception as e:
        print(f"Wikipedia error: {e}")
    return results

# ── MAIN search() ──
def search(query, enrich=True):
    expanded = expand_query(query.strip())
    dt       = _now()
    search_q = f"{expanded} {dt['month_year']}" if dt["year"] not in expanded else expanded

    print(f"Search: '{query}' → '{expanded}'")

    all_results = []

    # 1. Google News RSS
    rss = fetch_google_news_rss(search_q, max_items=5)
    if not rss:
        rss = fetch_google_news_rss(f"{expanded} {dt['year']}", max_items=5)

    # 2. Enrich — resolve redirects + trafilatura
    if rss and enrich:
        rss = enrich_articles(rss, max_workers=3)

    all_results.extend(rss)

    # 3. Wikipedia
    wiki = search_wikipedia(expanded)
    for w in wiki:
        if not any(w["url"] == r.get("url") for r in all_results):
            all_results.append(w)

    print(f"Total: {len(all_results)} results")

    if not all_results:
        return ""

    # Build context
    blocks = []
    for i, r in enumerate(all_results[:5], 1):
        body    = r.get("body", "")
        summary = r.get("summary", "")
        content = body if body and len(body) > len(summary) else summary
        block   = (
            f"[{i}. {r.get('title','')} | {r.get('source','')} | {r.get('published','')}]\n"
            f"{content}"
        )
        blocks.append(block)

    ctx = f"[LIVE SEARCH — {dt['date']}]\n\n" + "\n\n".join(blocks)
    print(f"Context: {len(ctx)} chars")
    return ctx[:5000]