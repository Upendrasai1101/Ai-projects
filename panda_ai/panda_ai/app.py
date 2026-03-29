from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
import os
import requests
from bs4 import BeautifulSoup
import urllib.parse

load_dotenv()

app = Flask(__name__, static_folder=".")
CORS(app)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ── DuckDuckGo Search ──
def duckduckgo_search(query, max_results=5):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        params = {"q": query, "kl": "in-en"}
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(params)
        res = requests.get(url, headers=headers, timeout=8)
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
        return ""

# ── OpenRouter Chat ──
def ask_openrouter(messages):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "Panda AI"
    }
    payload = {
        "model": "openrouter/auto",
        "messages": messages
    }
    res = requests.post(url, json=payload, headers=headers, timeout=30)
    data = res.json()
    if "choices" not in data:
        raise Exception(data.get("error", {}).get("message", str(data)))
    return data["choices"][0]["message"]["content"]

chat_histories = {}

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    session_id = data.get("session_id", "default")

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    try:
        search_results = duckduckgo_search(user_message)

        if search_results:
            prompt = f"{user_message}\n\n[SEARCH RESULTS]\n{search_results}"
        else:
            prompt = user_message

        today = datetime.now().strftime("%B %d, %Y")
        system_msg = {
            "role": "system",
            "content": (
                f"You are Panda AI, a calm, wise and helpful AI assistant — peaceful and smart like a panda. "
                f"Today's date is {today}. "
                "When you receive [SEARCH RESULTS], use them to give accurate up-to-date answers. "
                "Be clear, friendly and concise."
            )
        }

        if session_id not in chat_histories:
            chat_histories[session_id] = []

        chat_histories[session_id].append({"role": "user", "content": prompt})
        messages = [system_msg] + chat_histories[session_id][-10:]
        reply = ask_openrouter(messages)
        chat_histories[session_id].append({"role": "assistant", "content": reply})

        return jsonify({
            "reply": reply,
            "session_id": session_id,
            "searched": bool(search_results)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/reset", methods=["POST"])
def reset():
    data = request.get_json()
    session_id = data.get("session_id", "default")
    if session_id in chat_histories:
        del chat_histories[session_id]
    return jsonify({"status": "reset", "session_id": session_id})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🐼 Panda AI is running at http://0.0.0.0:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)
