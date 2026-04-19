# --- FILE: search_tool.py --- V6 Deep Crawl Build
"""
search_tool.py — Panda AI V6
Deep Crawl Mode (time-sensitive queries):
  - RSS fetch → top 3 URLs → trafilatura deep extract (1500 chars each)
  - IST timezone via pytz — fully dynamic, no hardcoded dates
Quick Mode (factual/general queries):
  - RSS snippets only — fast, lightweight
  - No date forced for identity/factual queries
"""

import feedparser
import requests
import trafilatura
import re
import random
import time
import pytz
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Constants ──
REQUEST_TIMEOUT  = 8
DEEP_CRAWL_LIMIT = 1500    # chars per deep-crawled article
DEEP_CRAWL_URLS  = 3       # number of URLs to deep crawl
IST              = pytz.timezone("Asia/Kolkata")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile/15E148 Safari/604.1",
]

def get_ua():
    return random.choice(USER_AGENTS)

# ════════════════════════════════════════
# IST-AWARE DATE HELPERS
# All dynamic — no hardcoded dates/years
# ════════════════════════════════════════
def _now_ist():
    """Always returns current IST time regardless of server location."""
    return datetime.now(IST)

def _dt():
    """Return IST-based date context dict."""
    n = _now_ist()
    return {
        "date":       n.strftime("%B %d, %Y"),
        "year":       str(n.year),
        "month":      n.strftime("%B"),
        "month_year": n.strftime("%B %Y"),
        "day":        n.strftime("%A"),
        "full_date":  n.strftime("%A, %B %d, %Y"),
        "yesterday":  (n - timedelta(days=1)).strftime("%B %d"),
        "yest_full":  (n - timedelta(days=1)).strftime("%B %d, %Y"),
        "two_days":   (n - timedelta(days=2)).strftime("%B %d"),
    }

def clean_text(text, limit=900):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[|*©®\[\]{}\\]', ' ', text)
    for p in [r'accept\s+cookies?', r'privacy\s+policy', r'subscribe\s+now',
              r'sign\s+up', r'log\s+in', r'advertisement', r'sponsored',
              r'click\s+here', r'read\s+more', r'all\s+rights\s+reserved',
              r'copyright\s+\d{4}']:
        text = re.sub(p, ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text[:limit]

# ════════════════════════════════════════
# SMART TEMPORAL DETECTION
# ════════════════════════════════════════
TIME_SENSITIVE_KEYWORDS = {
    "match","today","yesterday","latest","current","score","weather",
    "live","now","update","result","winner","news","tonight","morning",
    "this week","recently","breaking","vs","versus","ipl","bpl","cpl",
    "election","price","stock","rate","schedule","points table",
    "playing xi","squad","series","tournament","standings","wicket",
    "runs","target","chase","over","innings","goal","final","semi",
}

def is_time_sensitive(query: str) -> bool:
    """Returns True if query needs deep crawl + temporal context."""
    q = query.lower()
    return any(kw in q for kw in TIME_SENSITIVE_KEYWORDS)

# ════════════════════════════════════════
# QUERY BUILDER
# Smart temporal injection — IST aware
# No special chars that break RSS URLs
# ════════════════════════════════════════
def expand_query(query: str) -> str:
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
        (r'\bap\b',               'Andhra Pradesh'),
        (r'\bts\b',               'Telangana'),
    ]
    for pattern, replacement in rules:
        q = re.sub(pattern, replacement, q, flags=re.IGNORECASE)
    return q.strip()

def sanitize_query(query: str) -> str:
    """Remove special chars that break RSS URL encoding."""
    q = re.sub(r'[\[\]{}()\|"\'`]', ' ', query)
    q = re.sub(r'\s{2,}', ' ', q).strip()
    return q

def build_search_queries(query: str, dt: dict) -> list:
    """
    Build search query variants.
    Time-sensitive → inject IST-based date context.
    Factual → broad search, no date forcing.
    """
    expanded  = expand_query(query)
    clean_exp = sanitize_query(expanded)
    clean_raw = sanitize_query(query.strip())
    year      = dt["year"]          # fully dynamic
    month     = dt["month"]         # fully dynamic
    yesterday = dt["yesterday"]     # fully dynamic
    queries   = []

    if is_time_sensitive(query):
        q_low = query.lower()

        if re.search(r'\b(yesterday|last night|previous)\b', q_low):
            # e.g. "yesterday's match" → "IPL match April 18 2026"
            queries.append(f"{clean_exp} {yesterday} {year}")
            queries.append(f"{clean_exp} {year}")

        elif re.search(r'\b(today|tonight|this morning|now|live)\b', q_low):
            # e.g. "today's score" → "IPL score April 19, 2026"
            queries.append(f"{clean_exp} {dt['date']}")
            queries.append(f"{clean_exp} {year}")

        else:
            # "latest", "current", "score", "match" etc.
            queries.append(f"{clean_exp} {month} {year}")
            queries.append(f"{clean_exp} {year}")

        # Fallback: raw + year
        queries.append(f"{clean_raw} {year}")

    else:
        # Factual queries — no date forcing
        queries.append(clean_exp)
        queries.append(clean_raw)
        queries.append(f"{clean_exp} {year}")  # light hint only

    # Core keywords fallback (widest net)
    core = re.sub(
        r'\b(who|what|when|where|why|how|is|are|was|were|did|does|'
        r'the|a|an|of|in|on|at|to|for|with|about|tell|me|give|find|show)\b',
        ' ', clean_exp, flags=re.IGNORECASE
    )
    core = re.sub(r'\s{2,}', ' ', core).strip()
    if core and len(core) > 4:
        queries.append(core)

    # Deduplicate
    seen, unique = set(), []
    for q in queries:
        c = q.strip()
        if c and c not in seen:
            seen.add(c)
            unique.append(c)

    return unique

# ════════════════════════════════════════
# SOURCE 1: Google News RSS
# Snippet-First: title + summary = valid data
# ════════════════════════════════════════
def fetch_google_news_rss(query: str, max_items: int = 10) -> list:
    results = []
    try:
        clean_q = re.sub(r'["\']', '', sanitize_query(query))
        encoded = requests.utils.quote(clean_q)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        print(f"RSS: {rss_url[:110]}")

        feed = feedparser.parse(rss_url)
        if not feed.entries:
            print("RSS: 0 entries")
            return []

        for entry in feed.entries[:max_items]:
            title     = entry.get("title", "").strip()
            summary   = clean_text(entry.get("summary", ""), 500)
            url       = entry.get("link", "")
            published = entry.get("published", "")[:16]

            if not title:
                continue

            full_snippet = f"{title}. {summary}" if (summary and summary != title) else title

            results.append({
                "title":     title,
                "summary":   full_snippet,
                "url":       url,
                "published": published,
                "source":    "Google News",
                "body":      "",
            })

        print(f"RSS: {len(results)} entries")
    except Exception as e:
        print(f"RSS error: {e}")

    return results

def fetch_google_news_robust(query: str, dt: dict, max_items: int = 10) -> list:
    """Try multiple query strategies until results found."""
    strategies = build_search_queries(query, dt)
    for i, q in enumerate(strategies):
        print(f"RSS attempt {i+1}/{len(strategies)}: '{q[:70]}'")
        results = fetch_google_news_rss(q, max_items=max_items)
        if results:
            print(f"✅ RSS success: attempt {i+1} → {len(results)} entries")
            return results
        if i < len(strategies) - 1:
            time.sleep(0.2)
    print("RSS: all strategies returned 0 entries")
    return []

# ════════════════════════════════════════
# SOURCE 2: DEEP CRAWL (time-sensitive only)
# trafilatura.fetch_url + extract → 1500 chars
# Top 3 URLs, parallel, IST-aware timestamps
# ════════════════════════════════════════
def _deep_crawl_one(item: dict) -> tuple:
    """
    Deep crawl a single URL using trafilatura.
    Returns (url, extracted_body).
    Limited to DEEP_CRAWL_LIMIT chars for speed.
    """
    url   = item.get("url", "")
    title = item.get("title", "")

    # Skip Google redirect URLs — trafilatura can't parse them
    if not url or "news.google.com" in url or not url.startswith("http"):
        return url, ""

    try:
        # Use trafilatura's built-in fetch (handles redirects + encoding)
        downloaded = trafilatura.fetch_url(
            url,
            decode=True,
            no_ssl=False,
        )
        if not downloaded:
            print(f"  Deep crawl: no download — {url[:50]}")
            return url, ""

        # Extract main article text
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_precision=False,
            include_formatting=False,
        )

        if text:
            # Limit to DEEP_CRAWL_LIMIT chars, clean noise
            body = clean_text(text, DEEP_CRAWL_LIMIT)
            if len(body) > 100:
                print(f"  ✅ Deep crawl: {len(body)} chars — {title[:35]}")
                return url, body
            else:
                print(f"  Deep crawl: too short ({len(body)} chars) — {title[:35]}")
        else:
            print(f"  Deep crawl: no text extracted — {title[:35]}")

    except Exception as e:
        print(f"  Deep crawl error ({url[:40]}): {e}")

    return url, ""

def deep_crawl_top_urls(rss_results: list, max_crawl: int = DEEP_CRAWL_URLS) -> list:
    """
    Deep crawl the top N URLs from RSS results using trafilatura.
    Only triggered for time-sensitive queries.
    Parallel execution for speed.
    """
    if not rss_results:
        return rss_results

    # Pick top N items that have valid URLs
    to_crawl = [r for r in rss_results[:max_crawl] if r.get("url") and "google.com" not in r.get("url","")]

    if not to_crawl:
        print("Deep crawl: no valid URLs to crawl")
        return rss_results

    print(f"🔍 Deep crawl: fetching {len(to_crawl)} URLs with trafilatura...")

    body_map = {}
    try:
        # Parallel crawl — faster than sequential
        with ThreadPoolExecutor(max_workers=min(3, len(to_crawl))) as ex:
            futures = {ex.submit(_deep_crawl_one, r): r["url"] for r in to_crawl}
            for fut in as_completed(futures, timeout=20):
                try:
                    url, body = fut.result(timeout=3)
                    if body:
                        body_map[url] = body
                except Exception:
                    pass
    except Exception as e:
        print(f"Deep crawl pool error: {e}")

    # Merge bodies back into results
    enriched = 0
    for r in rss_results:
        url = r.get("url", "")
        if url in body_map:
            r["body"] = body_map[url]
            enriched += 1
        else:
            r["body"] = r.get("body", "")

    print(f"Deep crawl complete: {enriched}/{len(to_crawl)} URLs enriched")
    return rss_results

# ════════════════════════════════════════
# SOURCE 3: Wikipedia (always — factual grounding)
# ════════════════════════════════════════
def fetch_wiki_intro(title: str, limit: int = 600) -> str:
    try:
        res = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action":"query","prop":"extracts","exintro":True,
                    "explaintext":True,"titles":title,"format":"json","redirects":1},
            headers={"User-Agent":"PandaAI/6.0"}, timeout=REQUEST_TIMEOUT,
        )
        if res.status_code == 200:
            pages = res.json().get("query",{}).get("pages",{})
            for page in pages.values():
                extract = page.get("extract","")
                if extract:
                    return clean_text(extract, limit)
    except Exception:
        pass
    return ""

def search_wikipedia(query: str) -> list:
    results = []
    try:
        clean_q = re.sub(
            r'\b(current|latest|today|yesterday|who is|the|2026|2025|April|March|news|update|recent)\b',
            '', query, flags=re.IGNORECASE
        ).strip()
        clean_q = sanitize_query(re.sub(r'\s{2,}', ' ', clean_q))
        if not clean_q:
            return []

        res = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action":"query","list":"search","srsearch":clean_q,
                    "format":"json","srlimit":3,"srprop":"snippet|timestamp"},
            headers={"User-Agent":"PandaAI/6.0"}, timeout=REQUEST_TIMEOUT,
        )
        if res.status_code == 200:
            for item in res.json().get("query",{}).get("search",[]):
                title   = item.get("title","")
                snippet = clean_text(item.get("snippet",""), 400)
                ts      = item.get("timestamp","")[:10]
                intro   = fetch_wiki_intro(title)
                content = intro if intro else snippet
                if title and content:
                    results.append({
                        "title":     f"Wikipedia: {title}",
                        "summary":   content, "body":"",
                        "url":       f"https://en.wikipedia.org/wiki/{title.replace(' ','_')}",
                        "published": ts, "source":"Wikipedia",
                    })
        print(f"Wikipedia: {len(results)} results")
    except Exception as e:
        print(f"Wikipedia error: {e}")
    return results

# ════════════════════════════════════════
# MAIN: search()
# Smart Mode Selection:
#   Time-sensitive → Deep Crawl (trafilatura) + RSS
#   Factual        → Quick snippets only
# ════════════════════════════════════════
def search(query: str, enrich_articles: bool = True) -> str:
    dt       = _dt()                        # IST-aware, fully dynamic
    expanded = expand_query(query.strip())
    temporal = is_time_sensitive(query)
    mode     = "DEEP-CRAWL" if temporal else "QUICK-SNIPPET"

    print(f"\n🔍 Search V6 [{mode}]: '{query}'")
    print(f"   IST Date: {dt['full_date']}")

    all_results = []

    # ── Step 1: RSS Fetch (multi-strategy) ──
    rss = fetch_google_news_robust(query, dt, max_items=10)

    # ── Step 2: Mode-based enrichment ──
    if temporal and rss and enrich_articles:
        # TIME-SENSITIVE → Deep Crawl top 3 URLs with trafilatura
        print(f"⚡ Deep crawl mode: extracting full article bodies...")
        rss = deep_crawl_top_urls(rss, max_crawl=DEEP_CRAWL_URLS)
    elif rss and enrich_articles:
        # FACTUAL → Quick snippet only (no heavy crawl)
        print("📄 Quick mode: using RSS snippets")

    all_results.extend(rss)

    # ── Step 3: Wikipedia (always) ──
    wiki = search_wikipedia(expanded)
    for w in wiki:
        if not any(w["url"] == r.get("url") for r in all_results):
            all_results.append(w)

    print(f"Total sources: {len(all_results)}")

    if not all_results:
        return ""

    # ── Build context ──
    # Priority: deep-crawled body > snippet summary > title
    blocks = []
    for i, r in enumerate(all_results[:10], 1):
        title     = r.get("title","")
        summary   = r.get("summary","")
        body      = r.get("body","")
        published = r.get("published","")
        source    = r.get("source","")

        # Use body if sufficiently rich (deep crawl succeeded)
        if body and len(body) > 200:
            content = body          # Full article content — best for scores/details
            tag     = "[DEEP]"
        else:
            content = summary       # Snippet — still valid
            tag     = "[SNIPPET]"

        blocks.append(
            f"[{i}. {title} | {source} | {published} {tag}]\n{content}"
        )

    # IST-aware context header
    ctx = (
        f"[LIVE SEARCH — {dt['full_date']} IST | Mode: {mode}]\n"
        f"[Note: DEEP = full article body extracted. SNIPPET = headline + summary.]\n\n"
        + "\n\n".join(blocks)
    )
    print(f"Context: {len(ctx)} chars, {len(blocks)} blocks")
    return ctx[:5500]   # slightly higher limit for deep crawl richness


# ── Standalone test ──
if __name__ == "__main__":
    dt = _dt()
    print(f"IST Now: {dt['full_date']} | Yesterday: {dt['yesterday']}")
    print("\n=== TIME-SENSITIVE TEST (Deep Crawl) ===")
    ctx1 = search("who won yesterday IPL match")
    print(ctx1[:800])
    print("\n=== FACTUAL TEST (Quick Snippet) ===")
    ctx2 = search("who is CM of Telangana")
    print(ctx2[:500])