# --- FILE: search_tool.py --- V8.2 Studio
"""
search_tool.py — Panda AI V8.2 Studio

Main + Backup Architecture:
  - Primary Layer: Google News RSS (fast, reliable)
  - Backup Layer: gnews library (triggered only when RSS fails/returns empty)
  - Behavior: RSS first → if no results, trigger gnews with top 5 articles
    (language='en', country='IN')

Deep Crawl Mode (time-sensitive queries):
  - RSS fetch → top 3 URLs → trafilatura deep extract (1500 chars each)
  - IST timezone via pytz — fully dynamic, no hardcoded dates

Quick Mode (factual/general queries):
  - RSS snippets only — fast, lightweight
  - No date forced for identity/factual queries

V8.2 CHANGES (additive only — accuracy_plot logic UNTOUCHED):
  ✅ Main + Backup Architecture: RSS as Primary, gnews as Backup
  ✅ Future Intelligence Layer: detects user intent for upcoming
     events and uses datetime.date.today() to filter/search future-dated
     content from search results.

V8.1 CHANGES (additive only — scoring/accuracy logic UNTOUCHED):
  ✅ Dynamic year injection: current IST year is automatically
     appended to ALL search query variants, ensuring Google News
     always returns results scoped to the live calendar year.
  ✅ Today + 7 Days priority filter: after RSS fetch, results are
     re-ranked so articles published within the next 7 IST days
     float to the top. This is a SEPARATE post-fetch layer —
     it never alters build_search_queries(), is_time_sensitive(),
     or any scoring/accuracy logic.
"""

import feedparser
import requests
import trafilatura
import re
import random
import time
import pytz
import sys
import os
from datetime import datetime, timedelta, date
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Fix: Add user's local site-packages to sys.path for gnews ──
sys.path.append(os.path.expanduser("~/.local/lib/python3.12/site-packages"))

from gnews import GNews

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
        "year":       str(n.year),                              # ← V8.1: always live year
        "month":      n.strftime("%B"),
        "month_year": n.strftime("%B %Y"),
        "day":        n.strftime("%A"),
        "full_date":  n.strftime("%A, %B %d, %Y"),
        "yesterday":  (n - timedelta(days=1)).strftime("%B %d"),
        "yest_full":  (n - timedelta(days=1)).strftime("%B %d, %Y"),
        "two_days":   (n - timedelta(days=2)).strftime("%B %d"),
        # V8.1 — Today + 7 Days priority window (separate filter layer)
        "week_dates": [(n + timedelta(days=i)).strftime("%B %d, %Y") for i in range(8)],
    }

# ════════════════════════════════════════
# FUTURE INTELLIGENCE LAYER (V8.2)
# Detects user intent for upcoming events and filters
# future-dated content using datetime.date.today()
# ════════════════════════════════════════
FUTURE_INTENT_KEYWORDS = {
    "upcoming", "next week", "this week", "schedule", "fixtures",
    "upcoming matches", "future matches", "next match", "next game",
    "upcoming events", "future events", "next event", "calendar",
    "tournament", "series", "championship", "finals", "semi-finals",
    "playoffs", "qualifier", "eliminator", "final match",
    "when is", "when will", "date of", "dates for", "timings",
    "tomorrow",
}

# Typo correction map for common date-related misspellings
DATE_TYPO_MAP = {
    "tody": "today",
    "tomarrow": "tomorrow",
    "tommorow": "tomorrow",
    "tommorrow": "tomorrow",
    "todya": "today",
    "toady": "today",
    "yesteray": "yesterday",
    "yesterdy": "yesterday",
}

def fix_date_typos(text: str) -> str:
    """
    Consistently fix date-related typos in user input.
    Should be called before building any search query.
    """
    result = text
    for typo, correct in DATE_TYPO_MAP.items():
        pattern = re.compile(r'\b' + re.escape(typo) + r'\b', re.IGNORECASE)
        result = pattern.sub(correct, result)
    return result


def detects_future_intent(query: str) -> bool:
    """
    Returns True if the query indicates interest in upcoming events.
    Uses keyword matching on user intent patterns.
    Applies typo correction before detection.
    """
    q = query.lower().strip()
    
    # Fix common typos in date-related words before detection
    for typo, correct in DATE_TYPO_MAP.items():
        if typo in q:
            q = q.replace(typo, correct)
    
    # Check explicit future intent keywords
    if any(kw in q for kw in FUTURE_INTENT_KEYWORDS):
        return True
    # Check for question patterns about future
    future_patterns = [
        r"\bwhen\b.*\b(next|upcoming|future|schedule|match|game|event)",
        r"\bwhat\b.*\b(next|upcoming|future|schedule|match|game|event)",
        r"\bnext\b.*\b(match|game|event|tournament|series|fixture)",
        r"\bschedule\b",
        r"\bfixtures\b",
        r"\bupcoming\b",
    ]
    return any(re.search(p, q) for p in future_patterns)

def get_upcoming_dates(days_ahead: int = 30) -> list:
    """
    Return a list of upcoming dates from today using datetime.date.today().
    Format: ["May 01, 2026", "May 02, 2026", ...]
    """
    today = date.today()
    upcoming = []
    for i in range(1, days_ahead + 1):
        future_date = today + timedelta(days=i)
        upcoming.append(future_date.strftime("%B %d, %Y"))
    return upcoming

def filter_upcoming_events(results: list, query: str) -> list:
    """
    Filter search results to prioritize upcoming events based on
    datetime.date.today(). Matches published dates that are in the future
    relative to today.
    """
    if not results:
        return results

    today = date.today()
    priority, rest = [], []

    for r in results:
        pub = r.get("published", "")
        if not pub:
            rest.append(r)
            continue

        # Try to extract date from published field
        # Format could be: "Apr 28"  or  "April 28, 2026" or "2026-04-28"
        try:
            # Try multiple date formats
            parsed_date = None
            for fmt in ["%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"]:
                try:
                    parsed_date = datetime.strptime(pub[:16], fmt).date()
                    break
                except (ValueError, TypeError):
                    continue

            if parsed_date and parsed_date >= today:
                priority.append(r)
            else:
                rest.append(r)
        except Exception:
            rest.append(r)

    if priority:
        print(f"🔮 Future Intelligence: {len(priority)} upcoming events filtered")
    return priority + rest

def build_future_query(query: str) -> str:
    """
    Build a search query optimized for upcoming events.
    Uses datetime.now() to dynamically calculate 'tomorrow' using timedelta(days=1).
    Constructs query using f-strings with calculated day, month, and year.
    Replaces 'tomorrow' or its typos from user input with generated date string.
    """
    # Use datetime.now() to fetch current system date
    now = datetime.now()
    # Calculate 'tomorrow' using relative timedelta(days=1)
    tomorrow_date = now + timedelta(days=1)
    
    # Format tomorrow in various formats for dynamic insertion
    tomorrow_full = tomorrow_date.strftime("%B %d %Y")    # e.g., "April 29 2026"
    tomorrow_month_day = tomorrow_date.strftime("%B %d")  # e.g., "April 29"
    tomorrow_short = tomorrow_date.strftime("%d %b %Y")   # e.g., "29 Apr 2026"
    
    q = query.lower()
    
    # Fix common typos in date-related words (including tomorrow variants)
    for typo, correct in DATE_TYPO_MAP.items():
        if typo in q:
            q = q.replace(typo, correct)
            query = query.replace(typo, correct)
    
    # Replace 'tomorrow' (case-insensitive) with the dynamic date string
    tomorrow_pattern = re.compile(r'\btomorrow\b', re.IGNORECASE)
    q = tomorrow_pattern.sub(tomorrow_full, q)
    query = tomorrow_pattern.sub(tomorrow_full, query)
    
    # Get next 7 days as formatted strings for context
    upcoming_week = [(now + timedelta(days=i)).strftime("%B %d") for i in range(1, 8)]
    
    # If query already has a specific month, don't override - add year context
    month_match = re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b', q)

    if month_match:
        # User specified month, add dynamic year using f-string
        return f"{query} {now.year}"
    else:
        # No specific month - add schedule/fixtures context with dynamic year using f-string
        return f"{query} schedule fixtures {now.year}"

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
# SMART TEMPORAL DETECTION  (UNCHANGED)
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
# QUERY BUILDER  (V8.1: year auto-injected)
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

def _inject_year(query: str, year: str) -> str:
    """
    V8.1 — Ensure the current IST year is present in query.
    Only appends if no 4-digit year already exists in the string.
    This is a lightweight, additive step — never removes existing context.
    """
    if re.search(r'\b\d{4}\b', query):
        return query          # year already present — leave it alone
    return f"{query} {year}"

def build_search_queries(query: str, dt: dict) -> list:
    """
    Build search query variants.
    Time-sensitive → inject IST-based date context.
    Factual → broad search, no date forcing.

    V8.1: All variants automatically carry the current IST year
    via _inject_year() — a separate additive step that runs AFTER
    the existing logic. Original branching and scoring untouched.

    V8.2: If future_intent detected, replace typo words (tody, tomarrow)
    with actual date strings based on datetime.date.today().
    """
    expanded  = expand_query(query)
    clean_exp = sanitize_query(expanded)
    clean_raw = sanitize_query(query.strip())
    year      = dt["year"]          # fully dynamic IST year
    month     = dt["month"]         # fully dynamic
    yesterday = dt["yesterday"]     # fully dynamic
    queries   = []

    # ── V8.2: Fix typos and replace with actual dates for future intent ──
    if detects_future_intent(query):
        q_lower = query.lower()
        today = date.today()
        
        # Replace typo words with actual date strings
        for typo, correct in DATE_TYPO_MAP.items():
            if typo in q_lower:
                if correct == "today":
                    # Replace with tomorrow's date (Today + 1) for future events
                    future_date = (today + timedelta(days=1)).strftime("%B %d")
                    query = re.sub(r'\b' + re.escape(typo) + r'\b', future_date, query, flags=re.IGNORECASE)
                elif correct == "yesterday":
                    # Replace with today's date for past context
                    query = re.sub(r'\b' + re.escape(typo) + r'\b', today.strftime("%B %d"), query, flags=re.IGNORECASE)
        
        # Rebuild expanded/clean queries with corrected query
        expanded  = expand_query(query)
        clean_exp = sanitize_query(expanded)
        clean_raw = sanitize_query(query.strip())

    if is_time_sensitive(query):
        q_low = query.lower()

        if re.search(r'\b(yesterday|last night|previous)\b', q_low):
            queries.append(f"{clean_exp} {yesterday} {year}")
            queries.append(f"{clean_exp} {year}")

        elif re.search(r'\b(today|tonight|this morning|now|live)\b', q_low):
            queries.append(f"{clean_exp} {dt['date']}")
            queries.append(f"{clean_exp} {year}")

        else:
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

    # ── V8.1: Ensure current year in every variant (additive only) ──
    queries = [_inject_year(q, year) for q in queries]

    # Deduplicate
    seen, unique = set(), []
    for q in queries:
        c = q.strip()
        if c and c not in seen:
            seen.add(c)
            unique.append(c)

    return unique

# ════════════════════════════════════════
# V8.1 — TODAY + 7 DAYS PRIORITY FILTER
# Separate post-fetch layer.
# DOES NOT touch scoring or accuracy logic.
# ════════════════════════════════════════
def _priority_sort(results: list, week_dates: list) -> list:
    """
    Float results whose 'published' field falls within the
    Today + 7 Days window to the top of the list.
    Results outside the window are kept in original order below.

    This is purely a re-ranking step applied AFTER RSS fetch.
    It never modifies result content, scores, or accuracy data.
    """
    if not week_dates or not results:
        return results

    priority, rest = [], []
    for r in results:
        pub = r.get("published", "")
        # published field format from feedparser: e.g. "Apr 23"  or  "April 23, 2026"
        # We do a loose substring match against each date in the window
        matched = any(
            wd[:6] in pub or wd in pub          # "April 2" or full date
            for wd in week_dates
        )
        if matched:
            priority.append(r)
        else:
            rest.append(r)

    if priority:
        print(f"⏩ Priority filter: {len(priority)} results in Today+7 window, {len(rest)} outside")
    return priority + rest

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
# SOURCE 1.5: BACKUP LAYER — gnews library
# Triggered ONLY when RSS returns no results or fails
# Fetches top 5 news articles (language='en', country='IN')
# ════════════════════════════════════════
def fetch_gnews_backup(query: str, max_items: int = 5) -> list:
    """
    Backup layer using gnews library.
    Only triggered when RSS primary layer fails or returns empty results.
    Returns top 5 news articles with language='en', country='IN'.
    """
    results = []
    try:
        print(f"📰 gnews Backup: attempting for query '{query[:50]}...'")
        
        # Initialize gnews client with specified parameters
        gnews_client = GNews(
            language='en',
            country='IN',
            max_results=max_items,
            period=7,  # Last 7 days
            exclude_websites=['google.com']
        )
        
        # Search for news articles
        news_items = gnews_client.get_news(query)
        
        if not news_items:
            print("gnews Backup: 0 results")
            return []
        
        for item in news_items[:max_items]:
            title = item.get('title', '')
            description = item.get('description', '')
            url = item.get('url', '')
            published_date = item.get('published date', '')
            publisher = item.get('publisher', {})
            publisher_name = publisher.get('title', 'gnews') if publisher else 'gnews'
            
            if not title:
                continue
            
            # Build summary from title + description
            full_snippet = f"{title}. {description}" if description else title
            
            results.append({
                "title": title,
                "summary": full_snippet,
                "url": url,
                "published": published_date[:16] if published_date else '',
                "source": f"gnews ({publisher_name})",
                "body": "",
            })
        
        print(f"gnews Backup: {len(results)} entries")
        
    except Exception as e:
        print(f"gnews Backup error: {e}")
    
    return results

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
        downloaded = trafilatura.fetch_url(
            url,
            decode=True,
            no_ssl=False,
        )
        if not downloaded:
            print(f"  Deep crawl: no download — {url[:50]}")
            return url, ""

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_precision=False,
            include_formatting=False,
        )

        if text:
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

    to_crawl = [r for r in rss_results[:max_crawl] if r.get("url") and "google.com" not in r.get("url","")]

    if not to_crawl:
        print("Deep crawl: no valid URLs to crawl")
        return rss_results

    print(f"🔍 Deep crawl: fetching {len(to_crawl)} URLs with trafilatura...")

    body_map = {}
    try:
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
            headers={"User-Agent":"PandaAI/8.1"}, timeout=REQUEST_TIMEOUT,
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
        # Get dynamic year for cleanup
        current_year = str(date.today().year)
        clean_q = re.sub(
            rf'\b(current|latest|today|yesterday|who is|the|{current_year}|{int(current_year)-1}|April|March|news|update|recent)\b',
            '', query, flags=re.IGNORECASE
        ).strip()
        clean_q = sanitize_query(re.sub(r'\s{2,}', ' ', clean_q))
        if not clean_q:
            return []

        res = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action":"query","list":"search","srsearch":clean_q,
                    "format":"json","srlimit":3,"srprop":"snippet|timestamp"},
            headers={"User-Agent":"PandaAI/8.1"}, timeout=REQUEST_TIMEOUT,
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
#
# V8.1 additions (separate layers, clearly marked):
#   1. Year auto-injection in build_search_queries()
#   2. Today+7 priority sort after RSS fetch
#   3. Future Intelligence Layer: detects future intent and filters upcoming events
# ════════════════════════════════════════
def search(query: str, enrich_articles: bool = True) -> str:
    # ── Step 0: Fix typos consistently before any query building ──
    query = fix_date_typos(query)
    
    dt       = _dt()                        # IST-aware, fully dynamic
    expanded = expand_query(query.strip())
    temporal = is_time_sensitive(query)
    mode     = "DEEP-CRAWL" if temporal else "QUICK-SNIPPET"

    # ── V8.2: Future Intelligence Layer ──
    future_intent = detects_future_intent(query)
    if future_intent:
        mode = "FUTURE-EVENTS"
        print(f"\n🔮 Future Intelligence triggered: '{query}'")
        # Build future-optimized query
        query = build_future_query(query)
        print(f"   Enhanced query: '{query}'")

    print(f"\n🔍 Search V8.2 [{mode}]: '{query}'")
    print(f"   IST Date: {dt['full_date']} | Year: {dt['year']}")
    print(f"   Priority Window: {dt['week_dates'][0]} → {dt['week_dates'][-1]}")

    all_results = []

    # ── Step 1: RSS Fetch (multi-strategy, year auto-injected) ──
    rss = fetch_google_news_robust(query, dt, max_items=10)

    # ── Step 1.5: BACKUP LAYER — gnews library
    # Only triggered if RSS returns no results or fails
    if not rss:
        print("⚠️ RSS returned no results — triggering gnews Backup Layer...")
        gnews_backup = fetch_gnews_backup(query, max_items=5)
        if gnews_backup:
            print(f"✅ gnews Backup success: {len(gnews_backup)} entries")
            # Add every backup result to all_results with body mapped from summary
            for result in gnews_backup:
                result['body'] = result.get('summary', '')
                all_results.append(result)
        else:
            print("❌ gnews Backup also returned no results")

    # ── Step 2: V8.1 — Today+7 priority filter (separate layer) ──
    rss = _priority_sort(rss, dt["week_dates"])

    # ── Step 2b: V8.2 — Future Intelligence Layer filter ──
    if future_intent and rss:
        rss = filter_upcoming_events(rss, query)

    # ── Step 3: Mode-based enrichment (UNCHANGED logic) ──
    if temporal and rss and enrich_articles:
        print(f"⚡ Deep crawl mode: extracting full article bodies...")
        rss = deep_crawl_top_urls(rss, max_crawl=DEEP_CRAWL_URLS)
    elif rss and enrich_articles:
        print("📄 Quick mode: using RSS snippets")

    all_results.extend(rss)

    # ── Step 3.5: BACKUP LAYER — gnews library
    # Triggered when RSS is empty OR when deep crawl fails to extract meaningful content
    full_bodies = [r for r in all_results if r.get("body") and len(r.get("body", "")) > 200]
    
    # Debug: Log current state
    print(f"   Debug: all_results={len(all_results)}, full_bodies={len(full_bodies)}, temporal={temporal}")
    
    if not rss or (temporal and not full_bodies):
        backup_label = "RSS empty" if not rss else "Deep crawl failed"
        print(f"⚠️ {backup_label} — triggering gnews Backup Layer...")
        gnews_results = fetch_gnews_backup(query, max_items=5)
        if gnews_results:
            print(f"✅ gnews Backup success: {len(gnews_results)} entries")
            # Add every backup result to all_results with body mapped from summary
            for result in gnews_results:
                result['body'] = result.get('summary', '')
                all_results.append(result)
            print(f"   Debug: all_results after gnews={len(all_results)}")
        else:
            print("❌ gnews Backup also returned no results")

    # ── Step 4: Wikipedia (always) ──
    wiki = search_wikipedia(expanded)
    for w in wiki:
        if not any(w["url"] == r.get("url") for r in all_results):
            all_results.append(w)

    print(f"Total sources: {len(all_results)}")

    if not all_results:
        return ""

    # ── Build context ──
    # Priority: deep-crawled body > snippet summary > title
    # ACCURACY / SCORING LOGIC UNTOUCHED
    blocks = []
    for i, r in enumerate(all_results[:10], 1):
        title     = r.get("title","")
        summary   = r.get("summary","")
        body      = r.get("body","")
        published = r.get("published","")
        source    = r.get("source","")

        if body and len(body) > 200:
            content = body
            tag     = "[DEEP]"
        else:
            content = summary
            tag     = "[SNIPPET]"

        blocks.append(
            f"[{i}. {title} | {source} | {published} {tag}]\n{content}"
        )

    # IST-aware context header with System Context
    now = datetime.now()
    tomorrow_date = now + timedelta(days=1)
    tomorrow_str = tomorrow_date.strftime("%B %d %Y")
    
    ctx = (
        f"[LIVE SEARCH V8.2 — {dt['full_date']} IST | Mode: {mode} | Year: {dt['year']}]\n"
        f"[Note: DEEP = full article body extracted. SNIPPET = headline + summary.]\n"
        f"[Future Events: {'Enabled' if future_intent else 'Disabled'}]\n"
        f"\n{'='*60}\n"
        f"System Context:\n"
        f"  Current IST Date: {dt['full_date']}\n"
        f"  Target Search Date: {tomorrow_str}\n"
        f"{'='*60}\n\n"
        + "\n\n".join(blocks)
    )
    print(f"Context: {len(ctx)} chars, {len(blocks)} blocks")
    return ctx[:5500]


# ── Standalone test ──
if __name__ == "__main__":
    dt = _dt()
    print(f"IST Now: {dt['full_date']} | Year: {dt['year']} | Yesterday: {dt['yesterday']}")
    print(f"Priority Window: {dt['week_dates'][0]} → {dt['week_dates'][-1]}")
    print("\n=== TIME-SENSITIVE TEST (Deep Crawl) ===")
    ctx1 = search("who won yesterday IPL match")
    print(ctx1[:800])
    print("\n=== FACTUAL TEST (Quick Snippet) ===")
    ctx2 = search("who is CM of Telangana")
    print(ctx2[:500])