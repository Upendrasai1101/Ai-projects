from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
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

# ── SearXNG Instances (searxng.world + searx.be removed) ──
SEARXNG_INSTANCES = [
    "https://priv.au/search",
    "https://baresearch.org/search",
    "https://search.mdosch.de/search",
    "https://searx.work/search",
    "https://searx.tiekoetter.com/search",
]

# ── Trusted domains for scoring ──
TRUSTED_DOMAINS = [
    "wikipedia.org", "reuters.com", "bbc.com", "ndtv.com", "thehindu.com",
    "hindustantimes.com", "espn.com", "espncricinfo.com", "techradar.com",
    "timesofindia.com", "indianexpress.com", "economictimes.com",
    "theguardian.com", "apnews.com", "bloomberg.com", "news18.com",
    "wionews.com", "ani.in", "pib.gov.in", "livemint.com",
]

STALE_YEARS = ["2023", "2022", "2021", "2020", "2019"]
FRESH_TERMS = [CURRENT_YEAR, PREV_YEAR, "present", "current", "latest"]

TIME_KEYWORDS = [
    "today", "yesterday", "latest", "current", "now", "news", "match",
    "score", "result", "winner", "minister", "cm", "pm", "president",
    "election", "live", "update", "recent", "ipl", "cricket", "price",
    "rate", "weather", "stock", "who is", "who are", "captain", "rank"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/html;q=0.9",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }

# ── Helpers ──
def needs_fresh(query):
    return any(kw in query.lower() for kw in TIME_KEYWORDS)

def expand_query(query):
    clean = query.split("\n")[0].strip()
    if CURRENT_YEAR in clean:
        return clean
    if needs_fresh(clean):
        return f"{clean} current {MONTH_YEAR}"
    return f"{clean} {CURRENT_YEAR}"

def clean_text(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:450]

# ── Fix 2: score_result takes only item + is_sensitive (2 args) ──
def score_result(item, is_time_sensitive):
    title = item.get("title", "")
    body = item.get("body", "")
    url = item.get("url", "")
    text = f"{title} {body}".lower()
    score = 0

    # +5 trusted domain
    for domain in TRUSTED_DOMAINS:
        if domain in url:
            score += 5
            break

    # +10 current year
    if CURRENT_YEAR in text or "2025" in text:
        score += 10

    # +5 month/year specific
    if MONTH_YEAR.lower() in text:
        score += 5

    # Wikipedia bonus
    if "wikipedia.org" in url:
        score += 8

    # -50 stale (only if no fresh terms)
    if is_time_sensitive:
        has_fresh = any(f in text for f in FRESH_TERMS)
        if not has_fresh:
            for stale in STALE_YEARS:
                if stale in text:
                    score -= 50
                    break

    return score

# ── SearXNG Search ──
def search_searxng(query, time_range=None):
    results = []
    shuffled = SEARXNG_INSTANCES.copy()
    random.shuffle(shuffled)
    print(f"DEBUG: Shuffled: {[s.split('/')[2] for s in shuffled]}")

    for instance in shuffled:
        if len(results) >= 5:
            break
        print(f"DEBUG: Trying {instance}")
        try:
            params = {
                "q": query,
                "format": "json",
                "engines": "google,bing,wikipedia",
                "language": "en-IN",
                "region": "in-en",
            }
            if time_range:
                params["time_range"] = time_range

            # Fix 1: timeout=25 to avoid timeouts
            res = requests.get(
                instance, params=params,
                headers=get_headers(),
                timeout=25,
                allow_redirects=True
            )

            if res.status_code in [403, 429, 503, 404]:
                print(f"DEBUG: {instance} -> {res.status_code}, skip")
                continue

            if not res.text.strip():
                print(f"DEBUG: {instance} -> empty response, skip")
                continue

            try:
                data = res.json()
            except Exception:
                print(f"DEBUG: {instance} -> JSON parse failed, skip")
                continue

            for item in data.get("results", [])[:8]:
                title = item.get("title", "").strip()
                content = clean_text(item.get("content", ""))
                url = item.get("url", "")
                if title and content:
                    results.append({
                        "title": title,
                        "body": content,
                        "url": url
                    })

            print(f"DEBUG: Found {len(results)} results from {instance}")
            if len(results) >= 3:
                break

        except requests.exceptions.Timeout:
            print(f"DEBUG: {instance} timed out")
            continue
        except requests.exceptions.ConnectionError:
            print(f"DEBUG: {instance} connection error")
            continue
        except Exception as e:
            print(f"DEBUG: {instance} error: {e}")
            continue

    return results

# ── Wikipedia Fallback (Fix 3: returns formatted data) ──
def search_wikipedia(query):
    results = []
    try:
        clean = re.sub(r'\s+\d{4}$', '', query.split("\n")[0].strip())
        print(f"DEBUG: Wikipedia search: {clean}")
        params = {
            "action": "query",
            "list": "search",
            "srsearch": clean,
            "format": "json",
            "srlimit": 4,
            "srprop": "snippet|timestamp"
        }
        res = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            headers={"User-Agent": "PandaAI-Bot/1.0 (https://panda-ai-iv5u.onrender.com)"},
            timeout=10
        )
        if res.status_code != 200 or not res.text.strip():
            return results
        try:
            data = res.json()
        except Exception:
            return results

        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            snippet = clean_text(item.get("snippet", ""))
            timestamp = item.get("timestamp", "")[:10]
            if snippet:
                results.append({
                    "title": f"Wikipedia: {title}",
                    "body": f"{snippet} (last updated: {timestamp})",
                    "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                })
        print(f"DEBUG: Wikipedia returned {len(results)} results")
    except Exception as e:
        print(f"DEBUG: Wikipedia error: {e}")
    return results

# ── Main Search with Scoring ──
def search_web(query):
    original = query.split("\n")[0].strip()
    expanded = expand_query(original)
    is_time_sensitive = needs_fresh(original)

    print(f"DEBUG: Query: {original}")
    print(f"DEBUG: Expanded: {expanded}")
    print(f"DEBUG: Time sensitive: {is_time_sensitive}")

    raw = []

    # Step 1: SearXNG
    raw = search_searxng(expanded, time_range="month" if is_time_sensitive else None)

    # Step 2: SearXNG without filter
    if len(raw) < 3 and is_time_sensitive:
        more = search_searxng(expanded, time_range=None)
        for r in more:
            if r not in raw:
                raw.append(r)

    # Step 3: Wikipedia fallback (Fix 3: always returns data to user)
    if len(raw) < 2:
        print("DEBUG: Insufficient results, Wikipedia fallback")
        wiki = search_wikipedia(original)
        raw.extend(wiki)

    if not raw:
        print("DEBUG: All sources failed")
        return ""

    # ── Scoring & Reranking ──
    scored = []
    for item in raw:
        # Fix 2: Only 2 args to score_result
        s = score_result(item, is_time_sensitive)
        title = item.get("title", "")
        body = item.get("body", "")
        url = item.get("url", "")
        if title and body:
            scored.append((s, title, body, url))

    scored.sort(key=lambda x: x[0], reverse=True)
    print(f"DEBUG: Top scores: {[s[0] for s in scored[:5]]}")

    top = scored[:4]

    # Check freshness
    has_fresh = any(
        CURRENT_YEAR in r[1] + r[2] or PREV_YEAR in r[1] + r[2]
        for r in top
    )
    disclaimer = not has_fresh and is_time_sensitive

    # Format results
    formatted = []
    for score, title, body, url in top:
        domain = ""
        try:
            domain = url.split("/")[2] if url else ""
        except:
            pass
        entry = f"• [{title}]"
        if domain:
            entry += f" ({domain})"
        entry += f" {body}"
        formatted.append(entry)

    if not formatted:
        return ""

    header = f"[Live Search: {TODAY} | SearXNG+Wikipedia | Use ONLY these results]\n"
    if disclaimer:
        header += "[Note: Showing most recent available data — live update may be delayed]\n"

    return header + "\n\n".join(formatted)

# ── News ──
def get_news_headlines():
    headlines = []
    try:
        results = search_searxng(f"India top news {MONTH_YEAR}", time_range="day")
        for item in results:
            title = item.get("title", "").strip()
            if title and len(title) > 15 and title not in headlines:
                headlines.append(title)
    except Exception as e:
        print(f"DEBUG: News error: {e}")

    if len(headlines) < 3:
        wiki = search_wikipedia(f"India {MONTH_YEAR} current events")
        for item in wiki:
            title = item.get("title", "").replace("Wikipedia: ", "").strip()
            if title and title not in headlines:
                headlines.append(title)

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
                "3. NEVER say 'I don't have current info' when context is provided.\n"
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
                "Search servers are temporarily unavailable. "
                "Answer from your knowledge but clearly prefix with: "
                "'Note: Live search unavailable. Based on my knowledge: '\n"
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