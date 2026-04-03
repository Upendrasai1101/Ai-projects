from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
import os
import requests
from bs4 import BeautifulSoup
import urllib.parse
import json
import re

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ── Query classifier ──
def is_current_event(query):
    """Check if query needs recent/time-sensitive results"""
    keywords = [
        "today", "yesterday", "latest", "current", "now", "recent", "2026",
        "news", "match", "score", "result", "winner", "ipl", "cricket",
        "minister", "cm", "pm", "president", "election", "died", "arrested",
        "launched", "announced", "happened", "update", "live"
    ]
    q = query.lower()
    return any(kw in q for kw in keywords)

def is_definition_query(query):
    """Check if query is a definition/factual question"""
    patterns = [r"^what is", r"^who is", r"^what are", r"^define", r"^explain", r"^how does", r"^what was"]
    q = query.lower().strip()
    return any(re.match(p, q) for p in patterns)

# ── Wikipedia Search (Fast, never blocked) ──
def search_wikipedia(query, max_results=3):
    try:
        clean = query.split("\n")[0].strip()
        # Remove year if added
        clean = re.sub(r'\s+\d{4}$', '', clean).strip()
        
        wiki_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": clean,
            "format": "json",
            "srlimit": max_results,
            "srprop": "snippet|timestamp"
        }
        res = requests.get(wiki_url, params=params, timeout=10)
        data = res.json()
        results = []
        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            snippet = BeautifulSoup(item.get("snippet", ""), "lxml").get_text()
            timestamp = item.get("timestamp", "")[:10]
            if snippet:
                results.append(f"• [Wikipedia - {title} (updated: {timestamp})] {snippet[:500]}")
        return results
    except Exception as e:
        print(f"Wikipedia error: {e}")
        return []

# ── DuckDuckGo Search ──
def search_duckduckgo(query, use_timelimit=False, max_results=5):
    try:
        clean = query.split("\n")[0].strip()
        current_year = datetime.now().year
        if str(current_year) not in clean:
            clean = f"{clean} {current_year}"

        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }

        results = []
        # Try with timelimit first if needed, then without
        filters = (["m"] if use_timelimit else []) + [None]
        
        for df in filters:
            if len(results) >= max_results:
                break
            try:
                params = {"q": clean, "kl": "in-en"}
                if df:
                    params["df"] = df
                url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(params)
                res = requests.get(url, headers=headers, timeout=10)
                res.encoding = "utf-8"
                # Limit content to 2500 chars for memory
                soup = BeautifulSoup(res.text[:25000], "lxml")
                for r in soup.select(".result__body")[:max_results]:
                    title_el = r.select_one(".result__title")
                    snippet_el = r.select_one(".result__snippet")
                    if snippet_el:
                        t = title_el.get_text(strip=True) if title_el else ""
                        s = snippet_el.get_text(strip=True)[:300]
                        entry = f"• [{t}] {s}"
                        if s and entry not in results:
                            results.append(entry)
            except:
                continue

        return results[:max_results]
    except Exception as e:
        print(f"DDG error: {e}")
        return []

# ── DuckDuckGo Instant API ──
def search_ddg_instant(query):
    try:
        clean = query.split("\n")[0].strip()
        params = {"q": clean, "format": "json", "no_html": "1", "skip_disambig": "1"}
        res = requests.get("https://api.duckduckgo.com/", params=params, timeout=10)
        data = res.json()
        results = []
        if data.get("AbstractText"):
            results.append(f"• [Summary] {data['AbstractText'][:500]}")
        for rt in data.get("RelatedTopics", [])[:2]:
            if isinstance(rt, dict) and rt.get("Text"):
                results.append(f"• [Related] {rt['Text'][:300]}")
        return results
    except:
        return []

# ── Main Search Function ──
def search_web(query, max_results=6):
    clean_query = query.split("\n")[0].strip()
    today_str = datetime.now().strftime("%B %d, %Y")
    results = []
    
    is_current = is_current_event(clean_query)
    is_definition = is_definition_query(clean_query)

    # Strategy: Wikipedia first for definitions/factual
    if is_definition or not is_current:
        wiki = search_wikipedia(clean_query)
        results.extend(wiki)

    # DuckDuckGo for current events
    ddg = search_duckduckgo(clean_query, use_timelimit=is_current)
    for r in ddg:
        if r not in results:
            results.append(r)

    # Instant API as supplement
    if len(results) < 3:
        instant = search_ddg_instant(clean_query)
        for r in instant:
            if r not in results:
                results.append(r)

    # Wikipedia fallback
    if len(results) < 3 and not is_definition:
        wiki = search_wikipedia(clean_query)
        for r in wiki:
            if r not in results:
                results.append(r)

    if results:
        header = f"[Search: {today_str} | Sources: Wikipedia + DuckDuckGo | Use ONLY these results for current facts]\n"
        return header + "\n\n".join(results[:max_results])
    return ""

# ── News Headlines ──
def get_news_headlines():
    today_str = datetime.now().strftime("%B %d, %Y")
    year = datetime.now().year
    headlines = []

    # DuckDuckGo news
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
            "Accept-Language": "en-US,en;q=0.9"
        }
        for df in ["d", "w"]:
            if len(headlines) >= 5:
                break
            params = {"q": f"India top news {year}", "kl": "in-en", "df": df}
            url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(params)
            res = requests.get(url, headers=headers, timeout=10)
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text[:20000], "lxml")
            for r in soup.select(".result__body")[:8]:
                title_el = r.select_one(".result__title")
                if title_el:
                    t = title_el.get_text(strip=True)
                    if t and t not in headlines and len(t) > 15:
                        headlines.append(t)
    except Exception as e:
        print(f"News DDG error: {e}")

    # Wikipedia current events fallback
    if len(headlines) < 3:
        try:
            wiki_url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query", "list": "search",
                "srsearch": f"India {datetime.now().strftime('%B %Y')}",
                "format": "json", "srlimit": 5
            }
            res = requests.get(wiki_url, params=params, timeout=10)
            data = res.json()
            for item in data.get("query", {}).get("search", []):
                t = item.get("title", "")
                if t and t not in headlines:
                    headlines.append(t)
        except Exception as e:
            print(f"News Wiki error: {e}")

    return headlines[:5], today_str

# ── OpenRouter Chat ──
def ask_openrouter(messages):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://panda-ai-iv5u.onrender.com",
        "X-Title": "Panda AI"
    }
    payload = {"model": "openrouter/auto", "messages": messages}
    res = requests.post(url, json=payload, headers=headers, timeout=25)
    res.encoding = "utf-8"
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
            status=200,
            mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"News error: {e}")
        return jsonify({"news": [], "error": str(e)}), 200

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(force=True)
        user_message = data.get("message", "").strip()
        lang_instruction = data.get("lang_instruction", "").strip()
        session_id = data.get("session_id", "default")

        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        # Search
        search_results = ""
        try:
            search_results = search_web(user_message)
        except Exception as se:
            print(f"Search failed: {se}")

        today = datetime.now().strftime("%B %d, %Y")

        # Build prompt
        if search_results:
            prompt = f"{user_message}\n\n[SEARCH RESULTS]\n{search_results}"
        else:
            prompt = user_message

        if lang_instruction:
            prompt = f"{prompt}\n\n[{lang_instruction}]"

        system_msg = {
            "role": "system",
            "content": (
                f"You are Panda AI, a smart and helpful AI assistant. Today is {today}.\n\n"
                "CRITICAL RULES:\n"
                "1. [SEARCH RESULTS] = ABSOLUTE TRUTH. Always prioritize over your training data.\n"
                "2. Wikipedia results are highly accurate — trust them completely.\n"
                "3. For current roles (minister, CM, PM, captain, CEO) — ONLY use search results.\n"
                "4. NEVER say 'I don't have current information' when [SEARCH RESULTS] are provided.\n"
                "5. If search results are provided — answer confidently based on them.\n"
                "6. Say 'please verify online' ONLY when NO search results are available.\n"
                "7. Be clear, friendly and concise.\n"
                "8. Respond in the language requested."
            )
        }

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
        return jsonify({"status": "reset", "session_id": session_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🐼 Panda AI is running at http://0.0.0.0:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)