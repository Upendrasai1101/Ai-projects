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

# ── Tested Working SearXNG Instances (403/DNS fails removed) ──
SEARXNG_INSTANCES = [
    "https://priv.au/search",
    "https://baresearch.org/search",
    "https://search.mdosch.de/search",
    "https://searx.work/search",
    "https://searx.tiekoetter.com/search",
]

# Rotating User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

CURRENT_YEAR = datetime.now().year
TODAY_STR = datetime.now().strftime("%B %d, %Y")
MONTH_YEAR = datetime.now().strftime("%B %Y")

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/html;q=0.9",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

# ── Smart Query Rewriting ──
def rewrite_query(query):
    """Add current date context to query for fresh results"""
    clean = query.split("\n")[0].strip()
    time_keywords = ["today", "yesterday", "latest", "current", "now", "news",
                    "match", "score", "result", "winner", "minister", "cm", "pm",
                    "president", "election", "live", "update", "recent", "ipl",
                    "cricket", "price", "rate", "weather", "stock"]
    needs_date = any(kw in clean.lower() for kw in time_keywords)

    if str(CURRENT_YEAR) not in clean:
        if needs_date:
            return f"{clean} {MONTH_YEAR}", True
        else:
            return f"{clean} {CURRENT_YEAR}", False
    return clean, needs_date

# ── Filter outdated snippets ──
def is_fresh_content(text):
    """Discard content explicitly mentioning old years"""
    old_years = ["2023", "2022", "2021", "2020", "2019"]
    fresh_years = [str(CURRENT_YEAR), str(CURRENT_YEAR - 1)]
    text_lower = text.lower()
    has_old = any(yr in text for yr in old_years)
    has_fresh = any(yr in text for yr in fresh_years)
    if has_old and not has_fresh:
        return False
    return True

def clean_snippet(text):
    """Remove HTML and boilerplate"""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:400]

# ── SearXNG Search ──
def search_searxng(query, time_range=None):
    results = []
    instances = SEARXNG_INSTANCES.copy()
    random.shuffle(instances)

    for instance in instances:
        if len(results) >= 5:
            break
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

            res = requests.get(
                instance, params=params,
                headers=get_headers(),
                timeout=12,
                allow_redirects=True
            )

            if res.status_code in [403, 429, 503]:
                print(f"SearXNG {instance} returned {res.status_code}")
                continue

            if res.status_code != 200 or not res.text.strip():
                continue

            try:
                data = res.json()
            except Exception:
                continue

            wiki_results = []
            other_results = []

            for item in data.get("results", [])[:8]:
                title = item.get("title", "").strip()
                content = clean_snippet(item.get("content", ""))
                engine = item.get("engine", "")

                if not title or not content:
                    continue

                if not is_fresh_content(content) and not is_fresh_content(title):
                    continue

                entry = f"• [{title}] {content}"

                # Wikipedia = Golden Source, prioritize
                if "wikipedia" in engine.lower() or "wikipedia" in title.lower():
                    wiki_results.append(entry)
                else:
                    other_results.append(entry)

            # Wikipedia first
            for r in wiki_results:
                if r not in results:
                    results.append(r)
            for r in other_results:
                if r not in results:
                    results.append(r)

            if len(results) >= 3:
                break

        except requests.exceptions.ConnectionError:
            print(f"SearXNG DNS/Connection error: {instance}")
            continue
        except requests.exceptions.Timeout:
            print(f"SearXNG timeout: {instance}")
            continue
        except Exception as e:
            print(f"SearXNG error {instance}: {e}")
            continue

    return results[:5]

# ── Wikipedia Fallback ──
def search_wikipedia(query):
    results = []
    try:
        clean = re.sub(r'\s+\d{4}$', '', query.split("\n")[0].strip())
        params = {
            "action": "query",
            "list": "search",
            "srsearch": clean,
            "format": "json",
            "srlimit": 3,
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
            snippet = clean_snippet(item.get("snippet", ""))
            timestamp = item.get("timestamp", "")[:10]
            if snippet:
                results.append(f"• [Wikipedia: {title} (updated: {timestamp})] {snippet}")

    except Exception as e:
        print(f"Wikipedia error: {e}")
    return results

# ── Main Search ──
def search_web(query):
    rewritten_query, needs_fresh = rewrite_query(query)
    results = []

    # Step 1: SearXNG with time filter
    searxng = search_searxng(rewritten_query, time_range="month" if needs_fresh else None)
    results.extend(searxng)

    # Step 2: SearXNG without time filter
    if len(results) < 3 and needs_fresh:
        more = search_searxng(rewritten_query, time_range=None)
        for r in more:
            if r not in results:
                results.append(r)

    # Step 3: Wikipedia fallback
    if len(results) < 3:
        wiki = search_wikipedia(query.split("\n")[0].strip())
        for r in wiki:
            if r not in results:
                results.append(r)

    if results:
        header = (
            f"[Search: {TODAY_STR} | Sources: SearXNG(Google+Bing+Wikipedia) | "
            f"CRITICAL: Use ONLY these results. Ignore training data for current events.]\n"
        )
        return header + "\n\n".join(results[:4])

    return ""

# ── News Headlines ──
def get_news_headlines():
    headlines = []

    try:
        results = search_searxng(
            f"India top news {MONTH_YEAR}",
            time_range="day"
        )
        for r in results:
            match = re.match(r'• \[(.+?)\]', r)
            if match:
                title = match.group(1).strip()
                if len(title) > 15 and title not in headlines:
                    headlines.append(title)
    except Exception as e:
        print(f"News error: {e}")

    if len(headlines) < 3:
        try:
            wiki = search_wikipedia(f"India {MONTH_YEAR} current events")
            for r in wiki:
                match = re.match(r'• \[Wikipedia: (.+?) \(', r)
                if match:
                    title = match.group(1).strip()
                    if title not in headlines:
                        headlines.append(title)
        except Exception as e:
            print(f"News Wiki error: {e}")

    return headlines[:5], TODAY_STR

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
            response=json.dumps({"news": [], "date": TODAY_STR}, ensure_ascii=False),
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
            print(f"Search failed: {se}")

        today = datetime.now().strftime("%B %d, %Y")

        if search_results:
            prompt = f"{user_message}\n\n[LIVE SEARCH CONTEXT]\n{search_results}"
            system_content = (
                f"You are Panda AI. Today is {today}.\n\n"
                "RULES:\n"
                "1. Use [LIVE SEARCH CONTEXT] as ABSOLUTE TRUTH.\n"
                "2. For current positions/events — ONLY use search context.\n"
                "3. NEVER say 'I don't have current info' when search context is provided.\n"
                "4. If context seems outdated — say 'Based on latest available data:'\n"
                "5. If context is empty — say 'I couldn't fetch live data, here is what I know:'\n"
                "6. Be clear, friendly, concise.\n"
                "7. Respond in language requested."
            )
        else:
            prompt = user_message
            system_content = (
                f"You are Panda AI. Today is {today}.\n"
                "Live search unavailable right now. "
                "Clearly state: 'I couldn't fetch live data, here is what I know:' "
                "Be honest about data freshness. Be clear, friendly, concise. "
                "Respond in language requested."
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