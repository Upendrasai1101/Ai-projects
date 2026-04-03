from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
import os
import requests
from bs4 import BeautifulSoup
import urllib.parse
import json

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

# Fix 1: Unicode support
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ── DuckDuckGo Search ──
def duckduckgo_search(query, max_results=6):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        clean_query = query.split("\n")[0].strip()
        current_year = datetime.now().year
        today_str = datetime.now().strftime("%B %d, %Y")

        # Add year if not present
        if str(current_year) not in clean_query:
            clean_query = f"{clean_query} {current_year}"

        results = []

        # Try multiple date filters - month first, then no filter
        for date_filter in ["m", None]:
            if len(results) >= 4:
                break
            try:
                params = {"q": clean_query, "kl": "in-en"}
                if date_filter:
                    params["df"] = date_filter
                url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(params)
                res = requests.get(url, headers=headers, timeout=10)
                res.encoding = "utf-8"
                soup = BeautifulSoup(res.text, "html.parser")
                for r in soup.select(".result__body")[:max_results]:
                    title = r.select_one(".result__title")
                    snippet = r.select_one(".result__snippet")
                    if snippet:
                        t = title.get_text(strip=True) if title else ""
                        s = snippet.get_text(strip=True)
                        entry = f"• [{t}] {s}"
                        if s and entry not in results:
                            results.append(entry)
            except Exception as e:
                print(f"Search attempt error: {e}")
                continue

        if results:
            header = f"[Search date: {today_str}. IMPORTANT: Use ONLY these search results for current facts. Do NOT use training data for current events.]\n"
            return header + "\n\n".join(results[:max_results])
        return ""

    except Exception as e:
        print(f"Search error: {e}")
        return ""

# ── OpenRouter Chat ──
def ask_openrouter(messages):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://panda-ai-iv5u.onrender.com",
        "X-Title": "Panda AI"
    }
    payload = {
        "model": "openrouter/auto",
        "messages": messages
    }
    res = requests.post(url, json=payload, headers=headers, timeout=30)
    res.encoding = 'utf-8'
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

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    user_message = data.get("message", "").strip()
    lang_instruction = data.get("lang_instruction", "").strip()
    session_id = data.get("session_id", "default")

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    try:
        # Search with original message only (no language instruction)
        search_results = duckduckgo_search(user_message)

        # Build prompt
        if search_results:
            prompt = f"{user_message}\n\n[SEARCH RESULTS]\n{search_results}"
        else:
            prompt = user_message

        # Add language instruction separately (doesn't affect search)
        if lang_instruction:
            prompt = f"{prompt}\n\n[{lang_instruction}]"

        today = datetime.now().strftime("%B %d, %Y")

        system_msg = {
            "role": "system",
            "content": (
                f"You are Panda AI, a smart, calm and helpful AI assistant. "
                f"Today is {today}. "
                "\n\nCRITICAL RULES:\n"
                "1. ALWAYS use [SEARCH RESULTS] as PRIMARY source. They are more accurate than your training.\n"
                "2. For current roles (minister, CM, PM, captain, CEO etc.) — ONLY use search results. NEVER use training data alone.\n"
                "3. Search results may be from last month — they are still MORE accurate than your 2024 training data.\n"
                "4. If search results are provided but seem incomplete — use them AND add: 'Based on recent search results as of {today}.'\n"
                "5. NEVER say 'I don\'t have current information' when search results ARE provided. Use the search results.\n"
                "6. Only say 'please verify online' if NO search results were provided at all.\n"
                "7. Be clear, friendly and concise.\n"
                "8. Respond fully in the language requested."
            )
        }

        if session_id not in chat_histories:
            chat_histories[session_id] = []

        chat_histories[session_id].append({"role": "user", "content": prompt})
        messages = [system_msg] + chat_histories[session_id][-10:]
        reply = ask_openrouter(messages)
        chat_histories[session_id].append({"role": "assistant", "content": reply})

        response = app.response_class(
            response=json.dumps({"reply": reply, "session_id": session_id, "searched": bool(search_results)}, ensure_ascii=False),
            status=200,
            mimetype='application/json; charset=utf-8'
        )
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/reset", methods=["POST"])
def reset():
    data = request.get_json(force=True)
    session_id = data.get("session_id", "default")
    if session_id in chat_histories:
        del chat_histories[session_id]
    return jsonify({"status": "reset", "session_id": session_id})


@app.route("/news", methods=["GET"])
def get_news():
    """Dedicated news endpoint for sidebar"""
    try:
        today_str = datetime.now().strftime("%B %d, %Y")
        query = f"India top news today {datetime.now().year}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        results = []
        for date_filter in ["d", "w", None]:
            if len(results) >= 5:
                break
            params = {"q": query, "kl": "in-en"}
            if date_filter:
                params["df"] = date_filter
            url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(params)
            res = requests.get(url, headers=headers, timeout=8)
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
            for r in soup.select(".result__body")[:8]:
                title = r.select_one(".result__title")
                if title:
                    t = title.get_text(strip=True)
                    if t and t not in results and len(t) > 10:
                        results.append(t)
            if len(results) >= 5:
                break

        response = app.response_class(
            response=json.dumps({
                "news": results[:5],
                "date": today_str
            }, ensure_ascii=False),
            status=200,
            mimetype="application/json; charset=utf-8"
        )
        return response
    except Exception as e:
        return jsonify({"news": [], "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🐼 Panda AI is running at http://0.0.0.0:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)