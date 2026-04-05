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

# ── SearXNG Public Instances (rotate to avoid blocks) ──
SEARXNG_INSTANCES = [
    "https://searx.be/search",
    "https://priv.au/search",
    "https://baresearch.org/search",
    "https://search.mdosch.de/search",
    "https://searx.tiekoetter.com/search",
]

def is_current_event(query):
    keywords = ["today", "yesterday", "latest", "current", "now", "recent",
                "news", "match", "score", "result", "winner", "ipl", "cricket",
                "minister", "cm", "pm", "president", "election", "died",
                "arrested", "launched", "announced", "happened", "update", "live",
                str(datetime.now().year)]
    q = query.lower()
    return any(kw in q for kw in keywords)

def is_definition_query(query):
    patterns = [r"^what is", r"^who is", r"^what are", r"^define",
                r"^explain", r"^how does", r"^what was", r"^tell me about"]
    q = query.lower().strip()
    return any(re.match(p, q) for p in patterns)

# ── Source 1: SearXNG ──
def search_searxng(query, use_timelimit=False):
    results = []
    instances = SEARXNG_INSTANCES.copy()
    random.shuffle(instances)

    for instance in instances[:3]:
        try:
            params = {
                "q": query,
                "format": "json",
                "engines": "google,duckduckgo,wikipedia",
                "language": "en-IN",
                "region": "in-en",
            }
            if use_timelimit:
                params["time_range"] = "day"

            res = requests.get(instance, params=params, timeout=10,
                             headers={"User-Agent": "Mozilla/5.0 (compatible; PandaAI/1.0)"})

            if res.status_code != 200:
                continue

            data = res.json()
            for item in data.get("results", [])[:6]:
                title = item.get("title", "")
                content = item.get("content", "")[:400]
                if content:
                    results.append(f"• [{title}] {content}")

            if results:
                break
        except Exception as e:
            print(f"SearXNG {instance} error: {e}")
            continue

    return results

# ── Source 2: Wikipedia API ──
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
        res = requests.get("https://en.wikipedia.org/w/api.php",
                          params=params, timeout=10)

        if res.status_code != 200 or not res.text.strip():
            return results

        data = res.json()
        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
            timestamp = item.get("timestamp", "")[:10]
            if snippet:
                results.append(f"• [Wikipedia: {title} (updated: {timestamp})] {snippet[:400]}")
    except Exception as e:
        print(f"Wikipedia error: {e}")
    return results

# ── Source 3: DuckDuckGo Instant API (fallback) ──
def search_ddg_instant(query):
    results = []
    try:
        clean = query.split("\n")[0].strip()
        params = {"q": clean, "format": "json", "no_html": "1", "skip_disambig": "1"}
        res = requests.get("https://api.duckduckgo.com/",
                          params=params, timeout=10)

        if res.status_code != 200 or not res.text.strip():
            return results

        data = res.json()
        if data.get("AbstractText"):
            results.append(f"• [Summary] {data['AbstractText'][:400]}")
        for rt in data.get("RelatedTopics", [])[:2]:
            if isinstance(rt, dict) and rt.get("Text"):
                results.append(f"• [Related] {rt['Text'][:300]}")
    except Exception as e:
        print(f"DDG Instant error: {e}")
    return results

# ── Main Search ──
def search_web(query, max_results=6):
    clean_query = query.split("\n")[0].strip()
    today_str = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year

    if str(current_year) not in clean_query:
        clean_query = f"{clean_query} {current_year}"

    is_current = is_current_event(clean_query)
    is_definition = is_definition_query(clean_query)
    results = []

    # Step 1: Wikipedia first for definitions
    if is_definition:
        wiki = search_wikipedia(clean_query)
        results.extend(wiki)

    # Step 2: SearXNG (primary)
    if len(results) < 4:
        searxng = search_searxng(clean_query, use_timelimit=is_current)
        for r in searxng:
            if r not in results:
                results.append(r)

    # Step 3: Wikipedia supplement
    if len(results) < 3:
        wiki = search_wikipedia(clean_query)
        for r in wiki:
            if r not in results:
                results.append(r)

    # Step 4: DDG Instant fallback
    if len(results) < 2:
        ddg = search_ddg_instant(clean_query)
        for r in ddg:
            if r not in results:
                results.append(r)

    if results:
        header = f"[Search: {today_str} | Sources: SearXNG+Wikipedia+DuckDuckGo | PRIORITY: Use ONLY these results]\n"
        return header + "\n\n".join(results[:max_results])
    return ""

# ── News Headlines ──
def get_news_headlines():
    today_str = datetime.now().strftime("%B %d, %Y")
    current_year = datetime.now().year
    headlines = []

    # Source 1: SearXNG news
    try:
        instances = SEARXNG_INSTANCES.copy()
        random.shuffle(instances)
        for instance in instances[:2]:
            try:
                params = {
                    "q": f"India top news {current_year}",
                    "format": "json",
                    "engines": "google,duckduckgo",
                    "language": "en-IN",
                    "time_range": "day"
                }
                res = requests.get(instance, params=params, timeout=10,
                                 headers={"User-Agent": "Mozilla/5.0 (compatible; PandaAI/1.0)"})
                if res.status_code == 200 and res.text.strip():
                    data = res.json()
                    for item in data.get("results", [])[:6]:
                        title = item.get("title", "")
                        if title and title not in headlines and len(title) > 10:
                            headlines.append(title)
                if headlines:
                    break
            except:
                continue
    except Exception as e:
        print(f"News SearXNG error: {e}")

    # Source 2: Wikipedia current events
    if len(headlines) < 3:
        try:
            params = {
                "action": "query", "list": "search",
                "srsearch": f"India {datetime.now().strftime('%B %Y')} news",
                "format": "json", "srlimit": 5
            }
            res = requests.get("https://en.wikipedia.org/w/api.php",
                             params=params, timeout=10)
            if res.status_code == 200 and res.text.strip():
                data = res.json()
                for item in data.get("query", {}).get("search", []):
                    t = item.get("title", "")
                    if t and t not in headlines:
                        headlines.append(t)
        except Exception as e:
            print(f"News Wiki error: {e}")

    return headlines[:5], today_str

# ── OpenRouter ──
def ask_openrouter(messages):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://panda-ai-iv5u.onrender.com",
        "X-Title": "Panda AI"
    }
    res = requests.post(url, json={"model": "openrouter/auto", "messages": messages},
                       headers=headers, timeout=25)
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

@app.route("/news", methods=["GET"])
def get_news():
    try:
        headlines, today_str = get_news_headlines()
        return app.response_class(
            response=json.dumps({"news": headlines, "date": today_str}, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"News route error: {e}")
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
        prompt = user_message
        if search_results:
            prompt = f"{user_message}\n\n[SEARCH RESULTS]\n{search_results}"
        if lang_instruction:
            prompt = f"{prompt}\n\n[{lang_instruction}]"

        system_msg = {
            "role": "system",
            "content": (
                f"You are Panda AI, a smart and helpful AI assistant. Today is {today}.\n\n"
                "CRITICAL RULES:\n"
                "1. [SEARCH RESULTS] = ABSOLUTE TRUTH. Always prioritize over training data.\n"
                "2. Wikipedia results are 100% accurate — trust them completely.\n"
                "3. For current roles (minister, CM, PM, captain, CEO) — ONLY use search results.\n"
                "4. NEVER say 'I don't have current information' when [SEARCH RESULTS] are provided.\n"
                "5. Answer confidently based on search results when provided.\n"
                "6. Say 'please verify online' ONLY when NO search results are available.\n"
                "7. Be clear, friendly and concise.\n"
                "8. Respond fully in the language requested."
            )
        }

        if session_id not in chat_histories:
            chat_histories[session_id] = []
        chat_histories[session_id].append({"role": "user", "content": prompt})
        messages = [system_msg] + chat_histories[session_id][-8:]
        reply = ask_openrouter(messages)
        chat_histories[session_id].append({"role": "assistant", "content": reply})

        return app.response_class(
            response=json.dumps({"reply": reply, "session_id": session_id, "searched": bool(search_results)}, ensure_ascii=False),
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