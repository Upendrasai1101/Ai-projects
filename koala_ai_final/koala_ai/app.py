from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
import os
import requests

load_dotenv()

app = Flask(__name__, static_folder=".")
CORS(app)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# ── Tavily Search ──
def tavily_search(query, max_results=5):
    try:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": True
        }
        res = requests.post(url, json=payload, timeout=8)
        data = res.json()
        results = []
        if data.get("answer"):
            results.append(f"📌 Summary: {data['answer']}")
        for r in data.get("results", []):
            if r.get("content"):
                results.append(f"• [{r.get('title','')}] {r['content'][:300]}")
        return "\n\n".join(results)
    except:
        return ""

# ── OpenRouter Chat ──
def ask_openrouter(messages):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "Koala AI"
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

# Store chat histories
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
        # Search
        search_results = tavily_search(user_message)

        # Build user prompt
        if search_results:
            prompt = f"{user_message}\n\n[SEARCH RESULTS]\n{search_results}"
        else:
            prompt = user_message

        # System message
        today = datetime.now().strftime("%B %d, %Y")
        system_msg = {
            "role": "system",
            "content": (
                f"You are Koala AI, a smart, calm and helpful AI assistant — wise and gentle like a koala. "
                f"Today's date is {today}. "
                "When you receive [SEARCH RESULTS], use them to give accurate up-to-date answers. "
                "Be clear, friendly and concise."
            )
        }

        # Get or create history
        if session_id not in chat_histories:
            chat_histories[session_id] = []

        chat_histories[session_id].append({"role": "user", "content": prompt})

        messages = [system_msg] + chat_histories[session_id][-10:]  # last 10 messages

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
    print("🐨 Koala AI is running at http://localhost:5000")
    app.run(debug=True, port=5000)
