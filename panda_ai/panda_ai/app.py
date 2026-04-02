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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Charset": "utf-8"
        }
        # Clean query - remove language instructions
        clean_query = query.split('\n')[0].strip()
        params = {"q": clean_query, "kl": "in-en"}
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(params)
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, "html.parser")

        results = []
        for r in soup.select(".result__body")[:max_results]:
            title = r.select_one(".result__title")
            snippet = r.select_one(".result__snippet")
            if snippet:
                t = title.get_text(strip=True) if title else ""
                s = snippet.get_text(strip=True)
                results.append(f"• [{t}] {s}")

        return "\n\n".join(results) if results else ""
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

        # Fix 4: Better system message for accuracy
        system_msg = {
            "role": "system",
            "content": (
                f"You are Panda AI, a smart, calm and helpful AI assistant. "
                f"Today's date is {today}. "
                "IMPORTANT PRIORITY RULES: "
                "1. When [SEARCH RESULTS] are provided, ALWAYS use them as your PRIMARY source. "
                "2. If search results mention a minister, politician, or current event — use ONLY the search result, IGNORE your training data. "
                "3. Never give outdated information when fresh search results are available. "
                "4. If search results contradict your training — trust the search results. "
                "5. Be clear, friendly and concise in your response. "
                "6. When asked to respond in a specific language, do so completely."
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🐼 Panda AI is running at http://0.0.0.0:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)