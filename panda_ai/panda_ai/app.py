from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
from duckduckgo_search import DDGS
import os
import requests
import json
import re
import random

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
app.config['JSON_AS_ASCII'] = False

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("WARNING: OPENROUTER_API_KEY not found!")

TODAY = datetime.now().strftime("%B %d, %Y")
CURRENT_YEAR = str(datetime.now().year)
PREV_YEAR = str(datetime.now().year - 1)
MONTH_YEAR = datetime.now().strftime("%B %Y")

# ── Trusted domains (bonus points) ──
TRUSTED_DOMAINS = [
    "wikipedia.org", "reuters.com", "bbc.com", "ndtv.com", "thehindu.com",
    "hindustantimes.com", "espn.com", "espncricinfo.com", "techradar.com",
    "timesofindia.com", "indianexpress.com", "livemint.com", "economictimes.com",
    "theguardian.com", "apnews.com", "bloomberg.com", "forbes.com",
    "toiplus.com", "news18.com", "wion.com", "ani.in", "pib.gov.in"
]

STALE_YEARS = ["2023", "2022", "2021", "2020", "2019", "2018"]
FRESH_TERMS = [CURRENT_YEAR, PREV_YEAR, "2025", "2026", "present", "current", "latest", "now"]

TIME_KEYWORDS = [
    "today", "yesterday", "latest", "current", "now", "news", "match",
    "score", "result", "winner", "minister", "cm", "pm", "president",
    "election", "live", "update", "recent", "ipl", "cricket", "price",
    "rate", "weather", "stock", "who is", "who are", "captain"
]

# ── Query helpers ──
def needs_fresh_data(query):
    q = query.lower()
    return any(kw in q for kw in TIME_KEYWORDS)

def expand_query(query):
    """Add current year/month for fresh results"""
    clean = query.split("\n")[0].strip()
    if CURRENT_YEAR in clean:
        return clean
    if needs_fresh_data(clean):
        return f"{clean} current {MONTH_YEAR}"
    return f"{clean} {CURRENT_YEAR}"

# ── Scoring System ──
def score_result(item, is_time_sensitive):
    title = item.get("title", "")
    body = item.get("body", "")
    url = item.get("url", "href", "")
    if not url:
        url = item.get("href", "")
    text = f"{title} {body}".lower()
    score = 0

    # +5 trusted domain
    for domain in TRUSTED_DOMAINS:
        if domain in url:
            score += 5
            break

    # +10 contains current year
    if CURRENT_YEAR in text or "2025" in text:
        score += 10

    # +5 contains month/year
    if MONTH_YEAR.lower() in text or "april 2026" in text:
        score += 5

    # -50 stale for time-sensitive queries
    if is_time_sensitive:
        for stale in STALE_YEARS:
            if stale in text:
                # Only penalize if no fresh term
                has_fresh = any(f in text for f in FRESH_TERMS)
                if not has_fresh:
                    score -= 50
                break

    # Wikipedia bonus
    if "wikipedia.org" in url:
        score += 8

    return score

def clean_text(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:450]

# ── DDGS Search ──
def search_ddgs(query, max_results=8):
    """Search using duckduckgo_search library"""
    results = []
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(
                query,
                region="in-en",
                safesearch="off",
                max_results=max_results
            ))
        print(f"DEBUG: DDGS returned {len(raw)} raw results")
        results = raw
    except Exception as e:
        print(f"DEBUG: DDGS error: {e}")
    return results

def search_ddgs_news(query, max_results=6):
    """Search news using DDGS"""
    results = []
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.news(
                query,
                region="in-en",
                safesearch="off",
                max_results=max_results
            ))
        print(f"DEBUG: DDGS news returned {len(raw)} results")
        results = raw
    except Exception as e:
        print(f"DEBUG: DDGS news error: {e}")
    return results

# ── Wikipedia Fallback ──
def search_wikipedia(query):
    results = []
    try:
        clean = re.sub(r'\s+\d{4}$', '', query.split("\n")[0].strip())
        params = {
            "action": "query", "list": "search",
            "srsearch": clean, "format": "json",
            "srlimit": 3, "srprop": "snippet|timestamp"
        }
        res = requests.get(
            "https://en.wikipedia.org/w/api.php", params=params,
            headers={"User-Agent": "PandaAI-Bot/1.0"}, timeout=8
        )
        if res.status_code != 200 or not res.text.strip():
            return results
        data = res.json()
        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            snippet = clean_text(item.get("snippet", ""))
            timestamp = item.get("timestamp", "")[:10]
            if snippet:
                results.append({
                    "title": f"Wikipedia: {title}",
                    "body": f"{snippet} (updated: {timestamp})",
                    "href": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                })
        print(f"DEBUG: Wikipedia returned {len(results)} results")
    except Exception as e:
        print(f"DEBUG: Wikipedia error: {e}")
    return results

# ── Main Search with Scoring ──
def search_web(query):
    original = query.split("\n")[0].strip()
    expanded = expand_query(original)
    is_time_sensitive = needs_fresh_data(original)

    print(f"DEBUG: Query: {original}")
    print(f"DEBUG: Expanded: {expanded}")
    print(f"DEBUG: Time sensitive: {is_time_sensitive}")

    raw_results = []

    # Step 1: DDGS text search
    raw_results = search_ddgs(expanded)

    # Step 2: DDGS news search for time-sensitive
    if is_time_sensitive:
        news = search_ddgs_news(expanded)
        raw_results.extend(news)

    # Step 3: Wikipedia fallback
    if len(raw_results) < 3:
        print("DEBUG: Insufficient results, adding Wikipedia")
        wiki = search_wikipedia(original)
        raw_results.extend(wiki)

    if not raw_results:
        print("DEBUG: All sources failed")
        return ""

    # ── Scoring & Reranking ──
    scored = []
    disclaimer_needed = False

    for item in raw_results:
        s = score_result(item, is_time_sensitive)
        title = item.get("title", "")
        body = clean_text(item.get("body", ""))
        url = item.get("url", item.get("href", ""))
        if title and body:
            scored.append((s, title, body, url))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    print(f"DEBUG: Top scores: {[s[0] for s in scored[:5]]}")

    # Check if best results are fresh
    top_results = scored[:4]
    has_fresh = any(
        CURRENT_YEAR in r[1] + r[2] or PREV_YEAR in r[1] + r[2]
        for r in top_results
    )

    if not has_fresh and is_time_sensitive:
        disclaimer_needed = True
        print("DEBUG: No fresh results found, adding disclaimer")

    # Build output
    formatted = []
    for score, title, body, url in top_results:
        domain = ""
        if url:
            try:
                domain = url.split("/")[2]
            except:
                pass
        entry = f"• [{title}]"
        if domain:
            entry += f" ({domain})"
        entry += f" {body}"
        formatted.append(entry)

    if not formatted:
        return ""

    header = f"[Live Search: {TODAY} | DDGS+Wikipedia | Use ONLY these results]\n"
    if disclaimer_needed:
        header += "[Note: Showing most recent available data — live update may be delayed]\n"

    return header + "\n\n".join(formatted)

# ── News Headlines ──
def get_news_headlines():
    headlines = []
    print("DEBUG: Fetching news")

    try:
        news = search_ddgs_news(f"India top news {MONTH_YEAR}")
        for item in news[:6]:
            title = item.get("title", "").strip()
            if title and len(title) > 15 and title not in headlines:
                headlines.append(title)
    except Exception as e:
        print(f"DEBUG: News error: {e}")

    if len(headlines) < 3:
        try:
            results = search_ddgs(f"India news today {MONTH_YEAR}")
            for item in results[:5]:
                title = item.get("title", "").strip()
                if title and len(title) > 15 and title not in headlines:
                    headlines.append(title)
        except Exception as e:
            print(f"DEBUG: News text fallback error: {e}")

    print(f"DEBUG: News count: {len(headlines)}")
    return headlines[:5], TODAY

# ── OpenRouter ──
def ask_openrouter(messages):
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY not configured")
    res = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json={"model": "openrouter/auto", "messages": messages},
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://panda-ai-iv5u.onrender.com",
            "X-Title": "Panda AI"
        },
        timeout=25
    )
    data = res.json()
    if "choices" not in data:
        raise Exception(data.get("error", {}).get("message", str(data)))
    return data["choices"][0]["message"]["content"]

chat_histories = {}

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/script.js")
def serve_script():
    return send_from_directory(".", "script.js")

@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/.well-known/<path:path>")
def well_known(path):
    return "", 204

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})

@app.route("/news", methods=["GET"])
def get_news():
    try:
        headlines, today_str = get_news_headlines()
        return app.response_class(
            response=json.dumps({"news": headlines, "date": today_str}, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"News error: {e}")
        return app.response_class(
            response=json.dumps({"news": [], "date": TODAY}, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(force=True)
        user_message = data.get("message", "").strip()
        lang_instruction = data.get("lang_instruction", "").strip()
        session_id = data.get("session_id", "default")

        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        search_results = ""
        try:
            search_results = search_web(user_message)
        except Exception as se:
            print(f"Search exception: {se}")

        today = datetime.now().strftime("%B %d, %Y")

        if search_results:
            prompt = f"Today is {today}.\n\nUser: {user_message}\n\n[LIVE SEARCH CONTEXT]\n{search_results}"
            system_content = (
                f"You are Panda AI. Today is {today}. You have live web access.\n\n"
                "RULES:\n"
                "1. [LIVE SEARCH CONTEXT] = ABSOLUTE TRUTH. Always use over training data.\n"
                "2. For current positions/events/scores — ONLY use search context.\n"
                "3. NEVER say 'I don't have current info' when search context is provided.\n"
                "4. NEVER mention your training cutoff date.\n"
                "5. If context says 'most recent available data' — mention that to user.\n"
                "6. Answer confidently from search context.\n"
                "7. Be clear, friendly, concise.\n"
                "8. Respond fully in the language requested."
            )
        else:
            prompt = f"Today is {today}.\n\nUser: {user_message}"
            system_content = (
                f"You are Panda AI. Today is {today}. You have live web access.\n"
                "Search is temporarily unavailable. "
                "Say: 'Search servers are currently busy. Please try again in a moment.' "
                "Do NOT give old training data as current facts. "
                "NEVER mention training cutoff. Be friendly. Respond in language requested."
            )

        if lang_instruction:
            prompt = f"{prompt}\n\n[{lang_instruction}]"

        if session_id not in chat_histories:
            chat_histories[session_id] = []

        chat_histories[session_id].append({"role": "user", "content": prompt})
        messages = [{"role": "system", "content": system_content}] + chat_histories[session_id][-8:]

        reply = ask_openrouter(messages)
        chat_histories[session_id].append({"role": "assistant", "content": reply})

        return app.response_class(
            response=json.dumps({
                "reply": reply,
                "session_id": session_id,
                "searched": bool(search_results)
            }, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )

    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/reset", methods=["POST"])
def reset():
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id", "default")
        if session_id in chat_histories:
            del chat_histories[session_id]
        return jsonify({"status": "reset"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🐼 Panda AI running at http://0.0.0.0:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)