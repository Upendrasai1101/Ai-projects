"""
search_tool.py — Panda AI Search Engine
Strategy:
  1. Google News RSS  → feedparser (XML, no scraping, no 403)
  2. trafilatura      → tries to fetch article body (may be blocked on Render datacenter IPs)
  3. Wikipedia API    → always works, no blocks, rich factual content
  4. Wikipedia intro  → paragraph-level extract for richer context
"""

import feedparser
import requests
import trafilatura
import re
import random
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── User-Agent rotation ──
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile/15E148 Safari/604.1",
]

def get_ua():
    return random.choice(USER_AGENTS)

def today():
    return datetime.now().strftime("%B %d, %Y")

def month_year():
    return datetime.now().strftime("%B %Y")

def year():
    return str(datetime.now().year)

# ── Clean raw text ──
def clean_text(text, limit=800):
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

# ── Expand abbreviations for better search accuracy ──
def expand_query(query):
    q = query
    expansions = [
        (r'\bpm\s+of\s+india\b',     'Prime Minister of India'),
        (r'\bpm\s+india\b',          'Prime Minister India'),
        (r'\bcurrent\s+pm\b',        'current Prime Minister India'),
        (r'\bwho\s+is\s+pm\b',       'who is Prime Minister of India'),
        (r'\bcm\s+of\s+(\w+)',       r'Chief Minister of \1'),
        (r'\bwho\s+is\s+cm\b',       'who is Chief Minister'),
        (r'\bcurrent\s+cm\b',        'current Chief Minister'),
        (r'\bipl\b',                 'IPL Indian Premier League'),
        (r'\b\bap\b\b',              'Andhra Pradesh'),
        (r'\bts\b',                  'Telangana'),
    ]
    for pattern, replacement in expansions:
        q = re.sub(pattern, replacement, q, flags=re.IGNORECASE)
    return q.strip()

# ─────────────────────────────────────────
# SOURCE 1: Google News RSS (no scraping)
# Returns titles + summaries from RSS feed
# ─────────────────────────────────────────
def fetch_google_news_rss(query, max_items=5):
    """
    Fetch Google News RSS — feedparser reads XML directly.
    No HTTP scraping = no 403 on Render.
    Returns list of {title, summary, url, published}
    """
    results = []
    try:
        encoded = requests.utils.quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        print(f"RSS: {rss_url[:80]}")

        feed = feedparser.parse(rss_url)

        if not feed.entries:
            print("RSS: 0 entries")
            return []

        for entry in feed.entries[:max_items]:
            title     = entry.get("title", "").strip()
            summary   = clean_text(entry.get("summary", ""), 400)
            url       = entry.get("link", "")
            published = entry.get("published", "")[:16]

            if not title:
                continue

            # summary often contains HTML — clean it
            if not summary:
                summary = title  # use title as minimal context

            results.append({
                "title":     title,
                "summary":   summary,
                "url":       url,
                "published": published,
                "source":    "Google News RSS",
            })

        print(f"RSS: {len(results)} entries parsed")

    except Exception as e:
        print(f"RSS error: {e}")

    return results

# ─────────────────────────────────────────
# SOURCE 2: trafilatura article extraction
# NOTE: May be blocked on Render datacenter
# IPs by news sites. Silently skips on fail.
# ─────────────────────────────────────────
def fetch_article_body(url, timeout=5):
    """
    Try to extract full article body using trafilatura.
    Silently returns "" if blocked or failed.
    """
    try:
        headers = {
            "User-Agent": get_ua(),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        res = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if res.status_code != 200:
            print(f"  Article fetch {res.status_code}: {url[:50]}")
            return ""

        text = trafilatura.extract(
            res.text,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        if text:
            cleaned = clean_text(text, 700)
            print(f"  trafilatura: {len(cleaned)} chars from {url[:50]}")
            return cleaned
    except requests.exceptions.Timeout:
        print(f"  Article timeout: {url[:50]}")
    except Exception as e:
        print(f"  Article error: {e}")
    return ""

def enrich_with_articles(rss_results, max_workers=3):
    """
    Parallel-fetch article bodies for RSS results.
    Uses ThreadPoolExecutor for speed.
    Skips any URL that fails — never crashes.
    """
    if not rss_results:
        return rss_results

    urls = [r["url"] for r in rss_results if r.get("url")]

    # Parallel fetch
    body_map = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(fetch_article_body, url): url for url in urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                body = future.result()
                if body:
                    body_map[url] = body
            except Exception:
                pass

    # Merge bodies back into results
    for r in rss_results:
        url = r.get("url", "")
        if url in body_map:
            r["body"] = body_map[url]
        else:
            r["body"] = ""  # fallback to summary only

    return rss_results

# ─────────────────────────────────────────
# SOURCE 3: Wikipedia API (always works)
# ─────────────────────────────────────────
def fetch_wiki_intro(title, limit=700):
    try:
        res = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "prop": "extracts",
                "exintro": True, "explaintext": True,
                "titles": title, "format": "json", "redirects": 1,
            },
            headers={"User-Agent": "PandaAI/1.0"},
            timeout=8,
        )
        if res.status_code == 200:
            pages = res.json().get("query", {}).get("pages", {})
            for page in pages.values():
                extract = page.get("extract", "")
                if extract:
                    return clean_text(extract, limit)
    except Exception:
        pass
    return ""

def search_wikipedia(query, limit=700):
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
            headers={"User-Agent": "PandaAI/1.0"},
            timeout=8,
        )
        if res.status_code == 200:
            items = res.json().get("query", {}).get("search", [])
            for item in items:
                title   = item.get("title", "")
                snippet = clean_text(item.get("snippet", ""), 400)
                ts      = item.get("timestamp", "")[:10]
                intro   = fetch_wiki_intro(title)
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

# ─────────────────────────────────────────
# MAIN: search() — called from app.py
# ─────────────────────────────────────────
def search(query, enrich_articles=True):
    """
    Master search function.
    Returns a formatted context string for Groq.
    Never raises — always returns something.
    """
    expanded = expand_query(query.strip())
    search_q = f"{expanded} {month_year()}" if year() not in expanded else expanded

    print(f"Search: '{query}' -> expanded: '{expanded}'")

    all_results = []

    # 1. Google News RSS
    rss = fetch_google_news_rss(search_q)
    if not rss:
        # retry with year only
        rss = fetch_google_news_rss(f"{expanded} {year()}")

    # 2. Enrich with article bodies (parallel, silent on fail)
    if rss and enrich_articles:
        time.sleep(random.uniform(0.2, 0.5))  # jitter
        rss = enrich_with_articles(rss, max_workers=3)

    all_results.extend(rss)

    # 3. Wikipedia fallback if RSS thin
    if len(all_results) < 2:
        print("RSS thin — adding Wikipedia")
        wiki = search_wikipedia(expanded)
        all_results.extend(wiki)

    # 4. Wikipedia always added for factual grounding
    if len(all_results) < 4:
        wiki = search_wikipedia(expanded)
        for w in wiki:
            if not any(w["url"] == r.get("url") for r in all_results):
                all_results.append(w)

    print(f"Total results: {len(all_results)}")

    if not all_results:
        return ""

    # Build context string
    blocks = []
    for i, r in enumerate(all_results[:5], 1):
        title     = r.get("title", "")
        summary   = r.get("summary", "")
        body      = r.get("body", "")
        published = r.get("published", "")
        source    = r.get("source", "")

        # Use body if available, else summary
        content = body if body and len(body) > len(summary) else summary

        block = f"[{i}. {title} | {source} | {published}]\n{content}"
        blocks.append(block)

    context = f"[LIVE SEARCH — {today()}]\n\n" + "\n\n".join(blocks)
    print(f"Context built: {len(context)} chars")
    return context[:4500]


# ── Quick test ──
if __name__ == "__main__":
    ctx = search("current Prime Minister of India 2026")
    print("\n=== CONTEXT ===")
    print(ctx[:1000])