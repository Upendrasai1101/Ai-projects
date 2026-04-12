"""
app.py — Panda AI V4.4 (Hugging Face Spaces Edition)
Port: 7860 (HF default)
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
import os, requests, json, re, random, time, hashlib
from search_tool import search, fetch_google_news_rss

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
app.config['JSON_AS_ASCII'] = False

# ── Groq Keys ──
GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
]
GROQ_KEYS = [k for k in GROQ_KEYS if k]
if not GROQ_KEYS:
    print("WARNING: No Groq API keys found!")
else:
    print(f"✅ Groq keys loaded: {len(GROQ_KEYS)} key(s)")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_MODEL         = "llama-3.3-70b-versatile"

# ── 2-Minute Smart Cache ──
_cache    = {}
CACHE_TTL = 120

def cache_key(q):
    return hashlib.md5(q.lower().strip().encode()).hexdigest()

def get_cache(q):
    k = cache_key(q)
    if k in _cache:
        age = time.time() - _cache[k]["ts"]
        if age < CACHE_TTL:
            print(f"🟢 Cache HIT ({age:.0f}s): {q[:40]}")
            return _cache[k]["context"]
        del _cache[k]
    return None

def set_cache(q, ctx):
    _cache[cache_key(q)] = {"context": ctx, "ts": time.time()}
    print(f"💾 Cache SET: {q[:40]}")

def get_date_context():
    n = datetime.now()
    return {
        "date":   n.strftime("%B %d, %Y"),
        "day":    n.strftime("%A"),
        "year":   str(n.year),
        "month":  n.strftime("%B %Y"),
        "anchor": (
            f"Today's Date: {n.strftime('%B %d, %Y')} | "
            f"Day: {n.strftime('%A')} | "
            f"Year: {n.year} | "
            f"Month: {n.strftime('%B')}"
        ),
    }

def needs_search(query):
    q = query.lower().strip()
    if re.match(
        r'^(hi|hello|hey|thanks|thank you|ok|okay|bye|'
        r'good\s+morning|good\s+night|what is your name|'
        r'who are you|what can you do|how are you)',
        q
    ):
        return False
    live_kw = [
        "today", "latest", "current", "now", "news", "score", "result",
        "winner", "minister", "cm", "pm", "president", "election", "live",
        "update", "recent", "ipl", "cricket", "price", "weather", "who is",
        "captain", "rank", "chief", "2026", "2025", "this year", "this month",
        "yesterday", "tomorrow", "match", "standing", "stock", "rate",
        "vs", "versus", "win", "lose", "andhra", "telangana", "india",
        "world", "government", "launch", "release", "announce",
        "died", "appointed", "elected", "arrested", "war", "attack",
    ]
    return any(kw in q for kw in live_kw)

# ── Groq with key rotation ──
def ask_groq(messages):
    if not GROQ_KEYS:
        raise Exception("No Groq API keys configured")
    keys = list(GROQ_KEYS)
    random.shuffle(keys)
    for key in keys:
        label = f"...{key[-6:]}"
        try:
            time.sleep(random.uniform(0.1, 0.3))
            res = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={
                    "model":       GROQ_MODEL,
                    "messages":    messages,
                    "max_tokens":  1024,
                    "temperature": 0.2,
                },
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type":  "application/json",
                },
                timeout=30,
            )
            if res.status_code == 429:
                print(f"Groq 429 key={label} — rotating...")
                time.sleep(1.5)
                continue
            if res.status_code in (401, 403):
                print(f"Groq {res.status_code} key={label} — skipping")
                continue
            if res.status_code >= 500:
                print(f"Groq server error {res.status_code}")
                continue
            data = res.json()
            if "choices" not in data:
                print(f"Groq no choices: {data.get('error',{}).get('message','')}")
                continue
            print(f"Groq ✅ key={label}")
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            print(f"Groq timeout key={label}")
        except Exception as e:
            print(f"Groq exception: {e}")
    raise Exception("All Groq keys exhausted")

def ask_openrouter(messages):
    if not OPENROUTER_API_KEY:
        raise Exception("No OpenRouter key")
    res = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json={"model": "openrouter/auto", "messages": messages},
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://huggingface.co/spaces",
            "X-Title":       "Panda AI",
        },
        timeout=25,
    )
    data = res.json()
    if "choices" not in data:
        raise Exception(data.get("error", {}).get("message", str(data)))
    return data["choices"][0]["message"]["content"]

def ask_ai(messages):
    try:
        return ask_groq(messages)
    except Exception as e:
        print(f"Groq failed: {e} — OpenRouter fallback")
    try:
        reply = ask_openrouter(messages)
        print("OpenRouter ✅ (fallback)")
        return reply
    except Exception as e:
        raise Exception("All AI providers failed.")

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

# ── Health check for UptimeRobot / HF monitoring ──
@app.route("/health")
def health():
    dc = get_date_context()
    return jsonify({
        "status":      "ok",
        "version":     "4.4-hf",
        "platform":    "Hugging Face Spaces",
        "port":        7860,
        "date":        dc["date"],
        "groq_keys":   len(GROQ_KEYS),
        "cache_items": len(_cache),
        "openrouter":  bool(OPENROUTER_API_KEY),
    }), 200

@app.route("/news")
def get_news():
    dc = get_date_context()
    try:
        results   = fetch_google_news_rss(f"India top news {dc['month']}", max_items=6)
        headlines = [r["title"] for r in results if len(r.get("title", "")) > 10]
        return app.response_class(
            response=json.dumps({"news": headlines[:5], "date": dc["date"]}, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"News error: {e}")
        return app.response_class(
            response=json.dumps({"news": [], "date": dc["date"]}, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )

@app.route("/chat", methods=["POST"])
def chat():
    try:
        body             = request.get_json(force=True)
        user_message     = body.get("message", "").strip()
        lang_instruction = body.get("lang_instruction", "").strip()
        session_id       = body.get("session_id", "default")

        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        dc = get_date_context()

        # ── Search with 2-min cache ──
        search_context   = ""
        search_attempted = False

        if needs_search(user_message):
            search_attempted = True
            cached = get_cache(user_message)
            if cached:
                search_context = cached
            else:
                try:
                    search_context = search(user_message)
                    if search_context:
                        set_cache(user_message, search_context)
                except Exception as se:
                    print(f"Search failed (non-fatal): {se}")

        # ── Build prompt based on search outcome ──
        if search_context:
            system_content = (
                f"You are Panda AI — a Real-Time Intelligence Engine.\n"
                f"{dc['anchor']}\n\n"
                "ABSOLUTE RULES:\n"
                "1. LIVE SEARCH CONTEXT from Google News + Wikipedia is provided below.\n"
                "2. Treat this context as ABSOLUTE CURRENT TRUTH.\n"
                "3. If your training data conflicts with the search context, "
                "   ALWAYS side with the search context.\n"
                "4. 2025/2026 data in context = definitive current answer.\n"
                "5. Context RELEVANT to question → answer confidently, cite source.\n"
                "6. Context IRRELEVANT → use your knowledge, prefix: 'Based on my knowledge:'\n"
                "7. Live scores/breaking news → ONLY from context, never guess.\n"
                "8. NEVER say 'As of my knowledge cutoff' or 'I don't have real-time access'.\n"
                "9. NEVER hallucinate names, scores, or positions.\n"
                "10. Multilingual: Telugu, Hindi, English — match user's language.\n"
                "11. Be concise, confident, direct."
            )
            prompt = (
                f"{dc['anchor']}\n\n"
                f"USER QUESTION: {user_message}\n\n"
                f"=== LIVE SEARCH CONTEXT ===\n{search_context}\n=== END ===\n\n"
                f"Answer from context if relevant. "
                f"If context is off-topic, use your knowledge with 'Based on my knowledge:' prefix."
            )

        elif search_attempted:
            system_content = (
                f"You are Panda AI — a Real-Time Intelligence Engine.\n"
                f"{dc['anchor']}\n\n"
                "SITUATION: Live search was attempted but returned no results.\n"
                "RULES:\n"
                "1. Briefly tell the user live search returned no results.\n"
                "2. Answer from training knowledge.\n"
                "3. Prefix: 'Based on my last knowledge (may not reflect latest data):'\n"
                "4. NEVER present outdated data as current fact.\n"
                "5. Suggest user verify from a live source for time-sensitive info.\n"
                "6. Match user's language: Telugu, Hindi, or English."
            )
            prompt = (
                f"{dc['anchor']}\n\n"
                f"USER QUESTION: {user_message}\n\n"
                f"Live search returned no results. Answer from knowledge with appropriate caveats."
            )

        else:
            system_content = (
                f"You are Panda AI — a helpful, intelligent AI assistant.\n"
                f"{dc['anchor']}\n\n"
                "Answer clearly, concisely, helpfully from your knowledge. "
                "Be friendly. Match user's language: Telugu, Hindi, or English."
            )
            prompt = f"{dc['anchor']}\n\nUser: {user_message}"

        if lang_instruction:
            prompt += f"\n\n[LANGUAGE INSTRUCTION: {lang_instruction}]"

        if session_id not in chat_histories:
            chat_histories[session_id] = []
        chat_histories[session_id].append({"role": "user", "content": prompt})
        messages = [{"role": "system", "content": system_content}] + chat_histories[session_id][-6:]

        reply = ask_ai(messages)
        chat_histories[session_id].append({"role": "assistant", "content": reply})

        return app.response_class(
            response=json.dumps({
                "reply":      reply,
                "session_id": session_id,
                "searched":   bool(search_context),
            }, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )

    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/reset", methods=["POST"])
def reset():
    try:
        body = request.get_json(force=True)
        sid  = body.get("session_id", "default")
        if sid in chat_histories:
            del chat_histories[sid]
        return jsonify({"status": "reset"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print(f"🐼 Panda AI V4.4 HF — http://0.0.0.0:{port}")
    print(f"   Groq: {len(GROQ_KEYS)} keys | Cache: {CACHE_TTL}s | OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}")
    app.run(debug=False, host="0.0.0.0", port=port)