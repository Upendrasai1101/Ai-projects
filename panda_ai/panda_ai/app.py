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

# SearXNG public instances
SEARXNG_INSTANCES = [
    "https://searx.be/search",
    "https://priv.au/search",
    "https://baresearch.org/search",
    "https://search.mdosch.de/search",
    "https://searx.tiekoetter.com/search",
    "https://searxng.world/search",
]

HEADERS = {
    "User-Agent": "PandaAI-Bot/1.0 (https://panda-ai-iv5u.onrender.com)",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── SearXNG Search ──
def search_searxng(query, time_range=None):
    results = []
    instances = SEARXNG_INSTANCES.copy()
    random.shuffle(instances)

    for instance in instances:
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

            res = requests.get(instance, params=params,
                             headers=HEADERS, timeout=8)

            if res.status_code != 200:
                continue

            try:
                data = res.json()
            except:
                continue

            for item in data.get("results", [])[:6]:
                title = item.get("title", "")
                content = item.get("content", "")[:400]
                url = item.get("url", "")
                if content and title:
                    results.append(f"• [{title}] {content}")

            if len(results) >= 4:
                break

        except Exception as e:
            print(f"SearXNG {instance} error: {e}")
            continue

    return results

# ── Wikipedia Search ──
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
            headers={"User-Agent": "PandaAI-Bot/1.0"},
            timeout=8
        )
        if res.status_code != 200 or not res.text.strip():
            return results

        try:
            data = res.json()
        except:
            return results

        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
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

    # Add year for freshness
    search_query = clean_query
    if str(current_year) not in clean_query:
        search_query = f"{clean_query} {current_year}"

    # Check if time-sensitive
    time_keywords = ["today", "yesterday", "latest", "current", "now",
                    "news", "match", "score", "result", "winner",
                    "minister", "election", "live", "update", "recent"]
    needs_fresh = any(kw in clean_query.lower() for kw in time_keywords)

    # Step 1: SearXNG with time filter if needed
    searxng_results = search_searxng(
        search_query,
        time_range="day" if needs_fresh else None
    )
    results.extend(searxng_results)

    # Step 2: SearXNG without time filter if not enough results
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
            f"Sources: SearXNG (Google+DDG+Bing+Wikipedia) | "
            f"CRITICAL: Use ONLY these results for current facts. "
            f"Do NOT use training data for current events.]\n"
        )
        return header + "\n\n".join(results[:6])

    return ""

# ── News Headlines ──
def get_news_headlines():
    today_str = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year
    headlines = []

    # SearXNG news
    try:
        results = search_searxng(
            f"India top news {current_year}",
            time_range="day"
        )
        for r in results:
            # Extract title from format "• [Title] content"
            match = re.match(r'• \[(.+?)\]', r)
            if match:
                title = match.group(1)
                if len(title) > 15 and title not in headlines:
                    headlines.append(title)
    except Exception as e:
        print(f"News SearXNG error: {e}")

    # Wikipedia fallback
    if len(headlines) < 3:
        try:
            wiki = search_wikipedia(
                f"India {datetime.now().strftime('%B %Y')} news events"
            )
            for r in wiki:
                match = re.match(r'• \[Wikipedia: (.+?) \(', r)
                if match:
                    title = match.group(1)
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

# ── Routes ──
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
            status=200,
            mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"News error: {e}")
        return app.response_class(
            response=json.dumps({"news": [], "date": datetime.now().strftime("%B %d, %Y")}, ensure_ascii=False),
            status=200,
            mimetype="application/json; charset=utf-8"
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

        # Always search for any factual/data-driven question
        search_results = ""
        search_failed = False
        try:
            search_results = search_web(user_message)
        except Exception as se:
            print(f"Search failed: {se}")
            search_failed = True

        today = datetime.now().strftime("%B %d, %Y")

        # Build prompt
        if search_results:
            prompt = (
                f"{user_message}\n\n"
                f"[LIVE SEARCH CONTEXT - Use this as primary source]\n"
                f"{search_results}"
            )
        else:
            prompt = user_message

        if lang_instruction:
            prompt = f"{prompt}\n\n[{lang_instruction}]"

        # System message
        if search_results:
            system_content = (
                f"You are Panda AI, a smart and helpful AI assistant. Today is {today}.\n\n"
                "CRITICAL RULES:\n"
                "1. [LIVE SEARCH CONTEXT] = ABSOLUTE TRUTH. Always use it over your training data.\n"
                "2. For current roles, positions, events — ONLY use the search context.\n"
                "3. NEVER say 'I don't have current information' when search context is provided.\n"
                "4. Answer confidently and directly based on the search context.\n"
                "5. Be clear, friendly and concise.\n"
                "6. Respond fully in the language requested."
            )
        else:
            system_content = (
                f"You are Panda AI, a smart and helpful AI assistant. Today is {today}.\n\n"
                "Note: Live search is currently unavailable. "
                "Answer based on your knowledge but clearly state: "
                "'I couldn't fetch live data, so here is what I know as of my training:'\n"
                "Be clear, friendly and concise. Respond in the language requested."
            )

        system_msg = {"role": "system", "content": system_content}

        if session_id not in chat_histories:
            chat_histories[session_id] = []

        chat_histories[session_id].append({"role": "user", "content": prompt})
        messages = [system_msg] + chat_histories[session_id][-8:]

        reply = ask_openrouter(messages)
        chat_histories[session_id].append({"role": "assistant", "content": reply})

        return app.response_class(
            response=json.dumps({
                "reply": reply,
                "session_id": session_id,
                "searched": bool(search_results)
            }, ensure_ascii=False),
            status=200,
            mimetype="application/json; charset=utf-8"
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