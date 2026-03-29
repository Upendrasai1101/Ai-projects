from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

app = Flask(__name__, static_folder=".")
CORS(app)

# Configure Gemini API from .env
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not found! .env file lo key pettavaa?")

genai.configure(api_key=API_KEY)

# Initialize Gemini model
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=(
        "You are Tiger AI, a powerful and intelligent AI assistant. "
        "You are sharp, confident, and helpful — like a tiger: precise, fast, and strong. "
        "Answer questions clearly and concisely. Be friendly but direct."
    )
)

# Store chat sessions in memory
chat_sessions = {}


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
        if session_id not in chat_sessions:
            chat_sessions[session_id] = model.start_chat(history=[])

        chat = chat_sessions[session_id]
        response = chat.send_message(user_message)

        return jsonify({
            "reply": response.text,
            "session_id": session_id
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/reset", methods=["POST"])
def reset():
    data = request.get_json()
    session_id = data.get("session_id", "default")
    if session_id in chat_sessions:
        del chat_sessions[session_id]
    return jsonify({"status": "reset", "session_id": session_id})


if __name__ == "__main__":
    print("🐯 Tiger AI is running at http://localhost:5000")
    app.run(debug=True, port=5000)
