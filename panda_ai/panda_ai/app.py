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
MONTH_YEAR = datetime.now().strftime("%B %Y")

# ── OUR OWN SearXNG + backups ──
SEARXNG_INSTANCES = [
    "https://panda-searxng.onrender.com/search",  # OUR OWN!
    "https://priv.au/search",
    "https://baresearch.org/search",
    "https://search.mdosch.de/search",
    "https://searx.work/search",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }

def clean_text(text):
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s+', ' ', text).strip()[:400]

def needs_fresh(query):
    keywords = ["today", "latest", "current", "now", "news", "score",
                "result", "winner", "minister", "cm", "pm", "president",
                "election", "live", "update", "recent", "ipl", "cricket",
                "price", "weather", "who is", "captain", "rank"]
    return any(kw in query.lower() for kw in keywords)

# ── SearXNG Search ──
def search_searxng(query, time_range=None):
    results = []

    # Try our own instance FIRST, then backups
    instances = [SEARXNG_INSTANCES[0]] + random.sample(SEARXNG_INSTANCES[1:], len(SEARXNG_INSTANCES)-1)

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
                timeout=10
            )

            if res.status_code != 200:
                print(f"SearXNG {instance.split('/')[2]} -> {res.status_code}")
                continue

            if not res.text.strip():
                continue

            try:
                data = res.json()
            except:
                continue

            for item in data.get("results", [])[:6]:
                title = item.get("title", "").strip()
                content = clean_text(item.get("content", ""))
                if title and content:
                    results.append(f"• [{title}] {content}")

            if results:
                print(f"SearXNG success: {instance.split('/')[2]} — {len(results)} results")
                break

        except requests.exceptions.Timeout:
            print(f"SearXNG timeout: {instance.split('/')[2]}")
            continue
        except requests.exceptions.ConnectionError:
            print(f"SearXNG connection error: {instance.split('/')[2]}")
            continue
        except Exception as e:
            print(f"SearXNG error: {e}")
            continue

    return results

# ── Wikipedia Fallback ──
def search_wikipedia(query):
    results = []
    try:
        clean = re.sub(r'\s+(current|\d{4}).*$', '',
                      query.split("\n")[0].strip(), flags=re.IGNORECASE)
        res = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search",
                "srsearch": clean, "format": "json",
                "srlimit": 4, "srprop": "snippet|timestamp"
            },
            headers={"User-Agent": "PandaAI/1.0 (https://panda-ai-iv5u.onrender.com)"},
            timeout=10
        )
        if res.status_code == 200 and res.text.strip():
            data = res.json()
            for item in data.get("query", {}).get("search", []):
                title = item.get("title", "")
                snippet = clean_text(item.get("snippet", ""))
                timestamp = item.get("timestamp", "")[:10]
                if title and snippet:
                    results.append(f"• [Wikipedia: {title} ({timestamp})] {snippet}")
            print(f"Wikipedia: {len(results)} results")
    except Exception as e:
        print(f"Wikipedia error: {e}")
    return results

# ── Main Search ──
def search_web(query):
    original = query.split("\n")[0].strip()
    is_fresh = needs_fresh(original)

    search_query = original
    if CURRENT_YEAR not in original:
        search_query = f"{original} {MONTH_YEAR if is_fresh else CURRENT_YEAR}"

    print(f"Searching: {search_query}")
    results = []

    # Step 1: SearXNG (our own instance first!)
    results = search_searxng(search_query, time_range="month" if is_fresh else None)

    # Step 2: SearXNG no filter
    if len(results) < 3:
        more = search_searxng(search_query)
        for r in more:
            if r not in results:
                results.append(r)

    # Step 3: Wikipedia fallback
    if len(results) < 2:
        wiki = search_wikipedia(original)
        results.extend(wiki)

    print(f"Total: {len(results)} results")

    if results:
        header = f"[Live Search: {TODAY} | LIVE SEARCH CONTEXT = ABSOLUTE TRUTH]\n"
        return header + "\n\n".join(results[:5])
    return ""

# ── News ──
def get_news_headlines():
    headlines = []

    results = search_searxng(f"India news {MONTH_YEAR}", time_range="day")
    for r in results:
        match = re.match(r'• \[(.+?)\]', r)
        if match:
            title = match.group(1).strip()
            if len(title) > 15 and title not in headlines:
                headlines.append(title)

    if len(headlines) < 3:
        wiki = search_wikipedia(f"India {MONTH_YEAR}")
        for r in wiki:
            match = re.match(r'• \[Wikipedia: (.+?) \(', r)
            if match:
                title = match.group(1).strip()
                if title not in headlines:
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
                "STRICT RULES:\n"
                "1. [LIVE SEARCH CONTEXT] = ABSOLUTE TRUTH. Always use over training data.\n"
                "2. Current positions/events/scores — ONLY from search context.\n"
                "3. NEVER say 'I don't have current info' when context is provided.\n"
                "4. NEVER mention training cutoff.\n"
                "5. Be clear, friendly, concise.\n"
                "6. Respond fully in language requested."
            )
        else:
            prompt = f"Today is {today}.\n\nUser: {user_message}"
            system_content = (
                f"You are Panda AI. Today is {today}.\n"
                "Live search temporarily unavailable. "
                "Answer from knowledge but prefix: 'Based on my knowledge (verify for latest):'\n"
                "Never present old data as current. Be friendly. Respond in language requested."
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