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

# ── Tested & Reliable SearXNG Instances (searxng.world removed) ──
SEARXNG_INSTANCES = [
    "https://priv.au/search",
    "https://baresearch.org/search",
    "https://search.mdosch.de/search",
    "https://searx.work/search",
    "https://searx.be/search",
    "https://searx.tiekoetter.com/search",
]

# Real browser User-Agent
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ── SearXNG Search ──
def search_searxng(query, time_range=None, max_results=6):
    results = []
    instances = SEARXNG_INSTANCES.copy()
    random.shuffle(instances)

    for instance in instances:
        if len(results) >= max_results:
            break
        try:
            params = {
                "q": query,
                "format": "json",
                "engines": "google,duckduckgo,wikipedia,bing",
                "language": "en-IN",
                "region": "in-en",
            }
            if time_range:
                params["time_range"] = time_range

            res = requests.get(
                instance, params=params,
                headers=BROWSER_HEADERS,
                timeout=8,
                allow_redirects=True
            )

            if res.status_code != 200:
                print(f"SearXNG {instance} returned {res.status_code}")
                continue

            if not res.text.strip():
                continue

            try:
                data = res.json()
            except Exception:
                continue

            for item in data.get("results", [])[:max_results]:
                title = item.get("title", "").strip()
                content = item.get("content", "").strip()[:400]
                if title and content:
                    results.append(f"• [{title}] {content}")

            if len(results) >= 3:
                break

        except requests.exceptions.ConnectionError as e:
            print(f"SearXNG connection error {instance}: DNS/Network")
            continue
        except requests.exceptions.Timeout:
            print(f"SearXNG timeout {instance}")
            continue
        except Exception as e:
            print(f"SearXNG error {instance}: {e}")
            continue

    return results

# ── Wikipedia Search ──
def search_wikipedia(query, max_results=3):
    results = []
    try:
        clean = re.sub(r'\s+\d{4}$', '', query.split("\n")[0].strip())
        params = {
            "action": "query",
            "list": "search",
            "srsearch": clean,
            "format": "json",
            "srlimit": max_results,
            "srprop": "snippet|timestamp"
        }
        res = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            headers={"User-Agent": "PandaAI-Bot/1.0 (https://panda-ai-iv5u.onrender.com)"},
            timeout=8
        )
        if res.status_code != 200 or not res.text.strip():
            return results

        try:
            data = res.json()
        except Exception:
            return results

        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            snippet = re.sub(r'<[^>]+>', '', item.get("snippet", "")).strip()
            timestamp = item.get("timestamp", "")[:10]
            if snippet:
                results.append(f"• [Wikipedia: {title} ({timestamp})] {snippet[:400]}")

    except Exception as e:
        print(f"Wikipedia error: {e}")

    return results

# ── Main Search ──
def search_web(query):
    clean_query = query.split("\n")[0].strip()
    today_str = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year
    results = []

    search_query = clean_query
    if str(current_year) not in clean_query:
        search_query = f"{clean_query} {current_year}"

    time_keywords = ["today", "yesterday", "latest", "current", "now", "news",
                    "match", "score", "result", "winner", "minister", "cm", "pm",
                    "election", "live", "update", "recent", "ipl", "cricket"]
    needs_fresh = any(kw in clean_query.lower() for kw in time_keywords)

    # Step 1: SearXNG primary
    searxng = search_searxng(search_query, time_range="day" if needs_fresh else None)
    results.extend(searxng)

    # Step 2: SearXNG without time filter if not enough
    if len(results) < 3 and needs_fresh:
        more = search_searxng(search_query, time_range=None)
        for r in more:
            if r not in results:
                results.append(r)

    # Step 3: Wikipedia fallback
    if len(results) < 3:
        wiki = search_wikipedia(clean_query)
        for r in wiki:
            if r not in results:
                results.append(r)

    if results:
        header = (
            f"[Live Search: {today_str} | "
            f"Sources: SearXNG+Wikipedia | "
            f"CRITICAL: Use ONLY these results. Do NOT use old training data.]\n"
        )
        return header + "\n\n".join(results[:6])

    return ""

# ── News Headlines ──
def get_news_headlines():
    today_str = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year
    headlines = []

    try:
        results = search_searxng(
            f"India top news {current_year}",
            time_range="day",
            max_results=8
        )
        for r in results:
            match = re.match(r'• \[(.+?)\]', r)
            if match:
                title = match.group(1).strip()
                if len(title) > 15 and title not in headlines:
                    headlines.append(title)
    except Exception as e:
        print(f"News SearXNG error: {e}")

    if len(headlines) < 3:
        try:
            wiki = search_wikipedia(f"India {datetime.now().strftime('%B %Y')} news")
            for r in wiki:
                match = re.match(r'• \[Wikipedia: (.+?) \(', r)
                if match:
                    title = match.group(1).strip()
                    if title not in headlines:
                        headlines.append(title)
        except Exception as e:
            print(f"News Wiki error: {e}")

    return headlines[:5], today_str

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
            response=json.dumps({"news": [], "date": datetime.now().strftime("%B %d, %Y")}, ensure_ascii=False),
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
                f"You are Panda AI, a smart helpful AI assistant. Today is {today}.\n\n"
                "RULES:\n"
                "1. [LIVE SEARCH CONTEXT] = ABSOLUTE TRUTH. Always use over training data.\n"
                "2. For current positions/events — ONLY use search context.\n"
                "3. NEVER say 'I don't have current info' when search context is provided.\n"
                "4. Answer confidently based on search context.\n"
                "5. Be clear, friendly, concise.\n"
                "6. Respond in language requested."
            )
        else:
            prompt = user_message
            system_content = (
                f"You are Panda AI, a smart helpful AI assistant. Today is {today}.\n"
                "Live search unavailable. Answer from knowledge but say: "
                "'I couldn't fetch live data, here is what I know:'\n"
                "Be clear, friendly, concise. Respond in language requested."
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