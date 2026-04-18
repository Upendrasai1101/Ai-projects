# --- FILE: search_tool.py --- V5 Smart Temporal Build
"""
search_tool.py — Panda AI V5
Smart Temporal Injection:
- Time-sensitive queries → append date/year
- Factual/identity queries → broad search, no date forcing
- Query sanitization: clean brackets + special chars
- Snippet-First: title + summary = complete evidence
"""

import feedparser
import requests
import trafilatura
import re
import random
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

REQUEST_TIMEOUT = 8

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile/15E148 Safari/604.1",
]

def get_ua():
    return random.choice(USER_AGENTS)

def _now():
    n = datetime.now()
    return {
        "date":       n.strftime("%B %d, %Y"),
        "year":       str(n.year),
        "month":      n.strftime("%B"),
        "month_year": n.strftime("%B %Y"),
        "yesterday":  (n - timedelta(days=1)).strftime("%B %d"),
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
# Only time-sensitive queries get date injected
# ════════════════════════════════════════
TIME_SENSITIVE_KEYWORDS = {
    "match","today","yesterday","latest","current","score","weather",
    "live","now","update","result","winner","news","tonight","morning",
    "this week","recently","just","breaking","vs","versus","ipl",
    "election","price","stock","rate","schedule","points table",
    "playing xi","squad","series","tournament","standings",
}

def is_time_sensitive(query: str) -> bool:
    """Returns True if query needs temporal context injected."""
    q = query.lower()
    return any(kw in q for kw in TIME_SENSITIVE_KEYWORDS)

def sanitize_query(query: str) -> str:
    """
    Remove special characters that break RSS URL encoding.
    Brackets, quotes, pipes, etc. → stripped cleanly.
    """
    # Remove brackets and their contents if they're empty or noise
    q = re.sub(r'[\[\]{}()\|"\'`]', ' ', query)
    # Remove multiple spaces
    q = re.sub(r'\s{2,}', ' ', q).strip()
    return q

# ════════════════════════════════════════
# QUERY EXPANSION
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

# ════════════════════════════════════════
# SMART QUERY BUILDER
# Temporal injection ONLY for time-sensitive queries
# ════════════════════════════════════════
def build_search_queries(query: str, dt: dict) -> list:
    """
    Smart query strategies:
    - Time-sensitive → inject date/year
    - Factual/identity → broad, no date forcing
    All queries sanitized of special chars.
    """
    expanded  = expand_query(query)
    clean_exp = sanitize_query(expanded)
    clean_raw = sanitize_query(query.strip())
    year      = dt["year"]
    month     = dt["month"]
    yesterday = dt["yesterday"]
    queries   = []

    if is_time_sensitive(query):
        # Time-sensitive: inject temporal context
        q_low = query.lower()

        if re.search(r'\b(yesterday|last night|previous)\b', q_low):
            queries.append(f"{clean_exp} {yesterday} {year}")
            queries.append(f"{clean_exp} {year}")
        elif re.search(r'\b(today|tonight|this morning|now|live)\b', q_low):
            queries.append(f"{clean_exp} {dt['date']}")
            queries.append(f"{clean_exp} {year}")
        else:
            # "latest", "current", "match", "score" etc.
            queries.append(f"{clean_exp} {month} {year}")
            queries.append(f"{clean_exp} {year}")

        # Fallback: raw query + year
        queries.append(f"{clean_raw} {year}")

    else:
        # Factual/identity queries: NO date forcing
        # "Who is CM of Telangana", "What is Python", "Biography of X"
        queries.append(clean_exp)                        # Expanded, no date
        queries.append(clean_raw)                        # Raw, no date
        queries.append(f"{clean_exp} {year}")            # With year as light hint

    # Core keywords fallback (widest net)
    core = re.sub(
        r'\b(who|what|when|where|why|how|is|are|was|were|did|does|'
        r'the|a|an|of|in|on|at|to|for|with|about|tell|me|give|find|show)\b',
        ' ', clean_exp, flags=re.IGNORECASE
    )
    core = re.sub(r'\s{2,}', ' ', core).strip()
    if core and len(core) > 4 and core not in queries:
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
# Snippet-First: title + summary = valid evidence
# ════════════════════════════════════════
def fetch_google_news_rss(query: str, max_items: int = 10) -> list:
    results = []
    try:
        # Sanitize then encode — no quotes, brackets, pipes
        clean_q = sanitize_query(query)
        clean_q = re.sub(r'["\']', '', clean_q)
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

            # Snippet-First: combine title + summary as primary data
            if summary and summary.strip() != title:
                full_snippet = f"{title}. {summary}"
            else:
                full_snippet = title

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
    """Try multiple strategies until results found."""
    strategies = build_search_queries(query, dt)
    for i, q in enumerate(strategies):
        print(f"RSS attempt {i+1}/{len(strategies)}: '{q[:75]}'")
        results = fetch_google_news_rss(q, max_items=max_items)
        if results:
            print(f"✅ RSS: {len(results)} entries on attempt {i+1}")
            return results
        if i < len(strategies) - 1:
            time.sleep(0.2)
    print("RSS: all strategies 0 entries")
    return []

# ════════════════════════════════════════
# SOURCE 2: trafilatura (bonus enrichment)
# ════════════════════════════════════════
def fetch_article_body(url: str, timeout: int = 5) -> str:
    try:
        if not url or "google.com" in url:
            return ""
        res = requests.get(
            url,
            headers={"User-Agent":get_ua(),"Accept":"text/html;q=0.9,*/*;q=0.8","Referer":"https://www.google.com/"},
            timeout=timeout, allow_redirects=True,
        )
        if res.status_code != 200:
            return ""
        text = trafilatura.extract(res.text, include_comments=False, include_tables=True, no_fallback=False)
        if text:
            cleaned = clean_text(text, 800)
            if len(cleaned) > 150:
                print(f"  trafilatura ✅ {len(cleaned)} chars")
                return cleaned
    except Exception:
        pass
    return ""

def enrich_with_articles(rss_results: list, max_workers: int = 3) -> list:
    if not rss_results:
        return rss_results
    urls     = [r["url"] for r in rss_results if r.get("url")]
    body_map = {}
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(fetch_article_body, u): u for u in urls}
            for fut in as_completed(futures, timeout=10):
                try:
                    body = fut.result(timeout=2)
                    if body: body_map[futures[fut]] = body
                except Exception:
                    pass
    except Exception as e:
        print(f"Enrich pool: {e}")
    enriched = 0
    for r in rss_results:
        r["body"] = body_map.get(r.get("url",""), "")
        if r["body"]: enriched += 1
    print(f"Enrichment: {enriched}/{len(rss_results)} (snippets are primary)")
    return rss_results

# ════════════════════════════════════════
# SOURCE 3: Wikipedia
# ════════════════════════════════════════
def fetch_wiki_intro(title: str, limit: int = 600) -> str:
    try:
        res = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action":"query","prop":"extracts","exintro":True,
                    "explaintext":True,"titles":title,"format":"json","redirects":1},
            headers={"User-Agent":"PandaAI/5.0"}, timeout=REQUEST_TIMEOUT,
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
            headers={"User-Agent":"PandaAI/5.0"}, timeout=REQUEST_TIMEOUT,
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
# ════════════════════════════════════════
def search(query: str, enrich_articles: bool = True) -> str:
    dt       = _now()
    expanded = expand_query(query.strip())
    temporal = "TIME-SENSITIVE" if is_time_sensitive(query) else "FACTUAL"
    print(f"\n🔍 Search [{temporal}]: '{query}'")

    all_results = []

    # 1. Robust RSS (smart temporal strategies)
    rss = fetch_google_news_robust(query, dt, max_items=10)

    # 2. Article enrichment (bonus)
    if rss and enrich_articles:
        time.sleep(random.uniform(0.1, 0.3))
        rss = enrich_with_articles(rss, max_workers=3)
    all_results.extend(rss)

    # 3. Wikipedia (always)
    wiki = search_wikipedia(expanded)
    for w in wiki:
        if not any(w["url"] == r.get("url") for r in all_results):
            all_results.append(w)

    print(f"Total: {len(all_results)} sources")
    if not all_results:
        return ""

    blocks = []
    for i, r in enumerate(all_results[:10], 1):
        title     = r.get("title","")
        summary   = r.get("summary","")
        body      = r.get("body","")
        published = r.get("published","")
        source    = r.get("source","")
        content   = body if (body and len(body) > 200) else summary
        blocks.append(f"[{i}. {title} | {source} | {published}]\n{content}")

    ctx = (
        f"[LIVE SEARCH — {dt['date']} | {dt['month_year']}]\n"
        f"[Context: News from last 48 hours is current. Headlines = valid facts.]\n\n"
        + "\n\n".join(blocks)
    )
    print(f"Context: {len(ctx)} chars, {len(blocks)} blocks")
    return ctx[:5000]


if __name__ == "__main__":
    # Test both types
    print("=== TIME-SENSITIVE TEST ===")
    ctx1 = search("who won yesterday IPL match")
    print(ctx1[:500])
    print("\n=== FACTUAL TEST ===")
    ctx2 = search("who is CM of Telangana")
    print(ctx2[:500])