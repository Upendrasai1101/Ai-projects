"""
app.py — Panda AI V4.4 Final
- GROQ_API_KEY_1 / _2 / _3
- Strict Real-Time Intelligence prompt
- Dynamic date injection in every prompt
- Smart search (live queries only) + 2-min cache
- Honest fallback when search fails
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

# ── Dynamic date (injected into EVERY prompt) ──
def get_date_context():
    n = datetime.now()
    return {
        "date":       n.strftime("%B %d, %Y"),
        "day":        n.strftime("%A"),
        "year":       str(n.year),
        "month":      n.strftime("%B %Y"),
        "anchor":     (
            f"Today's Date: {n.strftime('%B %d, %Y')} | "
            f"Day: {n.strftime('%A')} | "
            f"Year: {n.year} | "
            f"Month: {n.strftime('%B')}"
        ),
    }

# ── Smart search detection ──
def needs_search(query):
    q = query.lower().strip()
    # Skip search for pure conversational queries
    if re.match(
        r'^(hi|hello|hey|thanks|thank you|ok|okay|bye|'
        r'good\s+morning|good\s+night|what is your name|'
        r'who are you|what can you do|how are you|'
        r'what is photosynthesis|explain\s+\w+\s+theory)',
        q
    ):
        return False
    # Trigger search for anything current/factual/live
    live_kw = [
        "today", "latest", "current", "now", "news", "score", "result",
        "winner", "minister", "cm", "pm", "president", "election", "live",
        "update", "recent", "ipl", "cricket", "price", "weather", "who is",
        "captain", "rank", "chief", "2026", "2025", "this year", "this month",
        "yesterday", "tomorrow", "match", "standing", "stock", "rate",
        "vs", "versus", "win", "lose", "andhra", "telangana", "india",
        "world", "government", "policy", "launch", "release", "announce",
        "died", "appointed", "elected", "arrested", "war", "attack",
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

@app.route("/health")
def health():
    dc = get_date_context()
    return jsonify({
        "status":      "ok",
        "version":     "4.4-final",
        "date":        dc["date"],
        "groq_keys":   len(GROQ_KEYS),
        "cache_items": len(_cache),
        "openrouter":  bool(OPENROUTER_API_KEY),
    })

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

        # ── Dynamic date — injected into every prompt ──
        dc = get_date_context()

        # ── Search with 2-min cache ──
        search_context  = ""
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

        # ─────────────────────────────────────────────
        # CASE 1: Search ran AND returned results
        # → Strict real-time mode
        # ─────────────────────────────────────────────
        if search_context:
            system_content = (
                f"You are Panda AI — a Real-Time Intelligence Engine.\n"
                f"{dc['anchor']}\n\n"
                "YOUR IDENTITY:\n"
                "You are NOT a general-purpose chatbot. You are a real-time data analyst "
                "whose answers are grounded in live web data.\n\n"
                "ABSOLUTE RULES — READ CAREFULLY:\n"
                "1. A LIVE SEARCH CONTEXT from Google News + Wikipedia is provided below.\n"
                "2. This context contains data from the real web, retrieved RIGHT NOW.\n"
                "3. You MUST treat this context as ABSOLUTE CURRENT TRUTH.\n"
                "4. If your internal training data conflicts with the search context, "
                "   ALWAYS side with the search context. Your training may be outdated.\n"
                "5. If the context contains 2025 or 2026 data — use it as the definitive answer.\n"
                "6. Check if context is RELEVANT to the question:\n"
                "   - RELEVANT: answer directly, cite the source title.\n"
                "   - IRRELEVANT (different topic): use your knowledge but say "
                "     'Based on my knowledge:' as a prefix.\n"
                "7. For live scores or breaking news: ONLY use the context. Do not guess.\n"
                "8. NEVER say 'As of my knowledge cutoff' or 'I don't have real-time access'.\n"
                "9. NEVER hallucinate names, scores, positions, or statistics.\n"
                "10. Be concise, confident, and direct.\n"
                "11. Match the user's language: Telugu, Hindi, or English."
            )
            prompt = (
                f"{dc['anchor']}\n\n"
                f"USER QUESTION: {user_message}\n\n"
                f"=== LIVE SEARCH CONTEXT ===\n"
                f"{search_context}\n"
                f"=== END CONTEXT ===\n\n"
                f"INSTRUCTION: Scan the context above for the answer. "
                f"If found, state it confidently and cite the source. "
                f"If the context is about a different topic, answer from your knowledge "
                f"with a 'Based on my knowledge:' prefix."
            )

        # ─────────────────────────────────────────────
        # CASE 2: Search ran BUT returned no results
        # → Honest fallback — don't pretend
        # ─────────────────────────────────────────────
        elif search_attempted:
            system_content = (
                f"You are Panda AI — a Real-Time Intelligence Engine.\n"
                f"{dc['anchor']}\n\n"
                "SITUATION: A live web search was attempted for this query but returned "
                "no results (search engine may be temporarily unavailable).\n\n"
                "RULES:\n"
                "1. Be transparent: briefly mention that live search returned no results.\n"
                "2. Then answer from your training knowledge.\n"
                "3. Clearly flag your answer as: 'Based on my last knowledge (may not reflect "
                "   the latest data):'\n"
                "4. NEVER present potentially outdated data as current fact.\n"
                "5. Suggest the user verify from a live source for time-sensitive info.\n"
                "6. Be friendly and helpful despite the limitation.\n"
                "7. Match the user's language: Telugu, Hindi, or English."
            )
            prompt = (
                f"{dc['anchor']}\n\n"
                f"USER QUESTION: {user_message}\n\n"
                f"NOTE: Live search was attempted but returned no results. "
                f"Please answer from your training knowledge with appropriate caveats."
            )

        # ─────────────────────────────────────────────
        # CASE 3: No search needed (general knowledge)
        # → Direct, fast Groq answer
        # ─────────────────────────────────────────────
        else:
            system_content = (
                f"You are Panda AI — a helpful, intelligent AI assistant.\n"
                f"{dc['anchor']}\n\n"
                "Answer clearly, concisely, and helpfully from your knowledge. "
                "Be friendly. Match the user's language: Telugu, Hindi, or English."
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
    port = int(os.environ.get("PORT", 5000))
    print(f"🐼 Panda AI V4.4 Final — http://0.0.0.0:{port}")
    print(f"   Groq: {len(GROQ_KEYS)} keys | Cache: {CACHE_TTL}s TTL | OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}")
    app.run(debug=False, host="0.0.0.0", port=port)