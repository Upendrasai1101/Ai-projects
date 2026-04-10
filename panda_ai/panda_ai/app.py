"""
app.py — Panda AI V4.4
- GROQ_API_KEY_1 / _2 / _3  (matches .env)
- 2-minute smart cache
- Google News RSS + Wikipedia via search_tool.py
- Multilingual: Telugu, English, Hindi
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
import os, requests, json, re, random, time, hashlib
from search_tool import search, expand_query, fetch_google_news_rss

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
app.config['JSON_AS_ASCII'] = False

# ── Groq Keys — matches .env GROQ_API_KEY_1/2/3 ──
GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
]
GROQ_KEYS = [k for k in GROQ_KEYS if k]
if not GROQ_KEYS:
    print("WARNING: No Groq API keys found! Set GROQ_API_KEY_1/2/3 in environment.")
else:
    print(f"✅ Groq keys loaded: {len(GROQ_KEYS)} key(s)")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_MODEL         = "llama-3.3-70b-versatile"

# ── 2-Minute Smart Cache ──
_cache    = {}
CACHE_TTL = 120  # seconds

def cache_key(query):
    return hashlib.md5(query.lower().strip().encode()).hexdigest()

def get_cache(query):
    k = cache_key(query)
    if k in _cache:
        age = time.time() - _cache[k]["ts"]
        if age < CACHE_TTL:
            print(f"🟢 Cache HIT (age={age:.0f}s): {query[:40]}")
            return _cache[k]["context"]
        del _cache[k]
    return None

def set_cache(query, context):
    _cache[cache_key(query)] = {"context": context, "ts": time.time()}
    print(f"💾 Cache SET: {query[:40]}")

def now_anchor():
    n = datetime.now()
    return (
        f"TODAY={n.strftime('%B %d, %Y')} | "
        f"DAY={n.strftime('%A')} | "
        f"YEAR={n.year} | "
        f"MONTH={n.strftime('%B')}"
    )

# ── Detect if query needs live search ──
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
        "captain", "rank", "chief", "2026", "this year", "this month",
        "yesterday", "tomorrow", "match", "standing", "stock", "rate",
        "vs", "versus", "win", "lose", "andhra", "telangana", "india",
    ]
    return any(kw in q for kw in live_kw)

# ── Groq with 3-key rotation ──
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
                    "temperature": 0.3,
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

# ── OpenRouter last-resort fallback ──
def ask_openrouter(messages):
    if not OPENROUTER_API_KEY:
        raise Exception("No OpenRouter key configured")
    res = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json={"model": "openrouter/auto", "messages": messages},
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://panda-ai-iv5u.onrender.com",
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
        raise Exception("All AI providers failed. Please try again.")

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

@app.route("/health")
def health():
    return jsonify({
        "status":      "ok",
        "version":     "4.4",
        "groq_keys":   len(GROQ_KEYS),
        "cache_items": len(_cache),
        "openrouter":  bool(OPENROUTER_API_KEY),
        "time":        datetime.now().isoformat(),
    })

@app.route("/news")
def get_news():
    dt = datetime.now()
    try:
        results   = fetch_google_news_rss(
            f"India top news {dt.strftime('%B %Y')}", max_items=6
        )
        headlines = [r["title"] for r in results if len(r.get("title", "")) > 10]
        return app.response_class(
            response=json.dumps({
                "news": headlines[:5],
                "date": dt.strftime("%B %d, %Y"),
            }, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"News error: {e}")
        return app.response_class(
            response=json.dumps({"news": [], "date": dt.strftime("%B %d, %Y")}, ensure_ascii=False),
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

        anchor = now_anchor()

        # ── Search with 2-min cache ──
        search_context = ""
        if needs_search(user_message):
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

        # ── Build prompt ──
        if search_context:
            system_content = (
                f"You are Panda AI — the smart brother of Gemini. {anchor}\n\n"
                "PERSONA: Real-time AI analyst. Fast, accurate, multilingual.\n\n"
                "RULES:\n"
                "1. LIVE SEARCH CONTEXT from Google News RSS + Wikipedia is provided below.\n"
                "2. First check: is the context RELEVANT to the user's question?\n"
                "3. RELEVANT + answer found → answer confidently, cite the source title.\n"
                "4. IRRELEVANT context or answer not in context:\n"
                "   - Use your own training knowledge to answer directly.\n"
                "   - Do NOT say 'data not available' if you actually know the answer.\n"
                "5. For live scores / breaking news → use ONLY the context, do not guess.\n"
                "6. NEVER hallucinate names, scores, or positions.\n"
                "7. Multilingual: Telugu, English, Hindi — match the user's language.\n"
                "8. Be concise, friendly, and precise."
            )
            prompt = (
                f"DATE: {anchor}\n\n"
                f"USER QUESTION: {user_message}\n\n"
                f"=== LIVE CONTEXT (Google News + Wikipedia) ===\n"
                f"{search_context}\n"
                f"=== END CONTEXT ===\n\n"
                f"Answer from context if relevant. If context is off-topic, use your knowledge."
            )
        else:
            system_content = (
                f"You are Panda AI — the smart brother of Gemini. {anchor}\n"
                "Be helpful, friendly, multilingual (Telugu, English, Hindi). "
                "Answer clearly from your knowledge."
            )
            prompt = f"DATE: {anchor}\n\nUser: {user_message}"

        if lang_instruction:
            prompt += f"\n\n[LANGUAGE: {lang_instruction}]"

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
    port = int(os.environ.get("PORT", 5000))
    print(f"🐼 Panda AI V4.4 — http://0.0.0.0:{port}")
    print(f"   Groq: {len(GROQ_KEYS)} keys | Cache TTL: {CACHE_TTL}s | OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}")
    app.run(debug=False, host="0.0.0.0", port=port)