# --- FILE: app.py --- V6 Production Build
"""
Panda AI V6 — Production Build
IST Timezone: Always Asia/Kolkata regardless of server location
New routes: /weather (Open-Meteo), /news (categorized RSS), /generate-music (placeholder)
All V5.1 logic preserved: Groq rotation, search_tool, memory, file_processor
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
import pytz
import os, requests, json, re, random, time, hashlib

from search_tool    import search, fetch_google_news_rss, is_time_sensitive
from file_processor import process_file, process_mixed_files, allowed_file, UPLOAD_DIR
from memory         import load_memory, get_memory_context, extract_and_save_memory, clear_memory

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
CORS(app)
app.config['JSON_AS_ASCII'] = False

# ── Groq Keys (V5.1 unchanged) ──
GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
]
GROQ_KEYS = [k for k in GROQ_KEYS if k]
print(f"✅ Groq keys loaded: {len(GROQ_KEYS)} key(s)")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
HF_TOKEN           = os.getenv("HF_TOKEN", "")
GROQ_MODEL         = "llama-3.3-70b-versatile"

# ── IST Timezone (V6 fix) ──
IST = pytz.timezone("Asia/Kolkata")

def get_date_context():
    """
    Always returns IST time regardless of server location (US/EU/Asia).
    Uses pytz Asia/Kolkata — production-grade timezone handling.
    """
    n = datetime.now(IST)                          # ← IST always
    return {
        "date":       n.strftime("%B %d, %Y"),     # April 19, 2026
        "year":       str(n.year),                 # 2026
        "month":      n.strftime("%B"),            # April
        "month_year": n.strftime("%B %Y"),         # April 2026
        "day":        n.strftime("%A"),            # Sunday
        "time":       n.strftime("%I:%M %p IST"),  # 08:30 AM IST
        "full_date":  n.strftime("%A, %B %d, %Y"),# Sunday, April 19, 2026
        "anchor":     f"Today: {n.strftime('%A, %B %d, %Y')} | Time: {n.strftime('%I:%M %p IST')}",
    }

# ── Cache ──
_cache    = {}
CACHE_TTL = 120

def cache_key(q):
    return hashlib.md5(q.lower().strip().encode()).hexdigest()

def get_cache(q):
    k = cache_key(q)
    if k in _cache:
        age = time.time() - _cache[k]["ts"]
        if age < CACHE_TTL:
            print(f"🟢 Cache HIT ({int(age)}s): {q[:40]}")
            return _cache[k]["context"]
        del _cache[k]
    return None

def set_cache(q, ctx):
    _cache[cache_key(q)] = {"context": ctx, "ts": time.time()}
    print(f"💾 Cache SET: {q[:40]}")

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
        "today","latest","current","now","news","score","result","winner",
        "minister","cm","pm","president","election","live","update","recent",
        "ipl","cricket","price","weather","who is","captain","rank","chief",
        "2026","2025","this year","this month","yesterday","tomorrow","match",
        "standing","stock","rate","vs","versus","win","lose","andhra","telangana",
        "india","world","government","launch","release","announce","died",
        "appointed","elected","srh","rcb","mi","kkr","csk","dc","rr","gt","lsg","pbks",
        "squad","team","player","playing xi","schedule","points table",
    ]
    return any(kw in q for kw in live_kw)

# ── Groq key rotation (V5.1 unchanged) ──
def ask_groq(messages, temperature=0.4):
    if not GROQ_KEYS:
        raise Exception("No Groq keys")
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
                    "temperature": temperature,
                    "top_p":       0.9,
                },
                headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
                timeout=30,
            )
            if res.status_code == 429:
                print(f"Groq 429 key={label}"); time.sleep(1.5); continue
            if res.status_code in (401,403): continue
            if res.status_code >= 500: continue
            data = res.json()
            if "choices" not in data: continue
            print(f"Groq ✅ key={label}")
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            print(f"Groq timeout key={label}")
        except Exception as e:
            print(f"Groq error: {e}")
    raise Exception("All Groq keys exhausted")

def ask_openrouter(messages):
    if not OPENROUTER_API_KEY:
        raise Exception("No OpenRouter key")
    res = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json={"model":"openrouter/auto","messages":messages},
        headers={
            "Authorization":f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type":"application/json",
            "HTTP-Referer":"https://huggingface.co/spaces",
            "X-Title":"Panda AI"
        },
        timeout=25,
    )
    data = res.json()
    if "choices" not in data:
        raise Exception(data.get("error",{}).get("message",str(data)))
    print("OpenRouter ✅")
    return data["choices"][0]["message"]["content"]

def ask_ai(messages, temperature=0.4):
    try:
        return ask_groq(messages, temperature=temperature)
    except Exception as e:
        print(f"Groq failed: {e} → OpenRouter")
    try:
        return ask_openrouter(messages)
    except Exception as e:
        raise Exception(f"All providers failed: {e}")

chat_histories = {}

# ════════════════════════════════════════
# SYSTEM PROMPT — V6 Dynamic IST Persona
# ════════════════════════════════════════
def build_system_prompt(dc, memory_ctx, has_search, search_attempted):
    memory_section = f"\n\n{memory_ctx}" if memory_ctx else ""

    identity = (
        f"You are Panda AI, a smart and friendly AI assistant built in India.\n"
        f"Today is {dc['full_date']} | Current IST Time: {dc['time']}.\n"
        f"You are fully aware of current events, sports, politics, and general knowledge\n"
        f"as of {dc['day']}, {dc['month_year']}.\n\n"

        "NEVER say any of these — they break your persona:\n"
        "  ✗ 'as of my knowledge cutoff'\n"
        "  ✗ 'my training data only goes up to'\n"
        "  ✗ 'I don't have access to real-time information'\n"
        "  ✗ 'I cannot browse the internet'\n"
        "  ✗ 'as of 2023' or any past year as a limitation\n"
        "  ✗ 'you may want to check a news source'\n"
        "  ✗ 'I cannot confirm current details'\n"
        "  ✗ 'my information may be outdated'\n"
        "  ✗ 'I was trained on data up to'\n\n"

        f"INSTEAD speak confidently:\n"
        f"  ✅ 'As of {dc['full_date']}, X is Y.'\n"
        f"  ✅ 'Today is {dc['full_date']}. The current [role] is X.'\n"
        "  ✅ 'Based on the latest information, X happened.'\n"
        f"{memory_section}"
    )

    if has_search:
        return (
            identity +
            "\n\n━━━ YOUR CURRENT KNOWLEDGE ━━━\n"
            "The [LIVE SEARCH] data injected below is YOUR OWN current knowledge.\n"
            "It is not external data — it is what you know right now in April 2026.\n"
            "Speak from it naturally and authoritatively.\n\n"

            "HOW TO USE IT:\n"
            "• Headlines and snippets = verified facts you are aware of.\n"
            "• If snippet says 'X won' → you know X won. State it directly.\n"
            "• Person shown doing a role's duties → you know their role.\n"
            "• News from last 48 hours = current for today/yesterday questions.\n"
            "• Combine snippets naturally into a complete, flowing answer.\n\n"

            "LANGUAGE & TONE:\n"
            "• Match user's language: Telugu, Hindi, or English.\n"
            "• Be warm, direct, and conversational like a knowledgeable friend."
        )
    elif search_attempted:
        return (
            identity +
            "\n\n━━━ KNOWLEDGE NOTE ━━━\n"
            "Real-time feed returned no results for this query.\n"
            "Answer from your general knowledge confidently.\n"
            "For very recent events say: 'I don't have the very latest on this, but recently...'\n"
            "Never mention cutoff dates. Match language: Telugu, Hindi, or English."
        )
    else:
        return (
            identity +
            "\n\n━━━ RESPONSE STYLE ━━━\n"
            "Answer naturally and helpfully.\n"
            "For greetings → warm and friendly.\n"
            "For general knowledge → confident and clear.\n"
            "For coding → precise and helpful.\n"
            "Match language: Telugu, Hindi, or English."
        )

def build_chat_prompt(user_message, search_context, dc, lang_instruction=""):
    if search_context:
        prompt = (
            f"[{dc['anchor']}]\n\n"
            f"User: {user_message}\n\n"
            f"[YOUR CURRENT KNOWLEDGE — {dc['month_year']}]\n"
            f"{search_context}\n"
            f"[END]\n\n"
            f"Answer naturally and directly from your knowledge above.\n"
            f"Speak authoritatively — this is what you know right now."
        )
    else:
        prompt = f"[{dc['anchor']}]\n\nUser: {user_message}"
    if lang_instruction:
        prompt += f"\n\n[Respond in: {lang_instruction}]"
    return prompt

# ════════════════════════════════════════
# V6: WEATHER ROUTE — Open-Meteo (free)
# ════════════════════════════════════════
WEATHER_CODES = {
    0:("☀️","Clear Sky"),1:("🌤️","Mainly Clear"),2:("⛅","Partly Cloudy"),
    3:("☁️","Overcast"),45:("🌫️","Foggy"),48:("🌫️","Icy Fog"),
    51:("🌦️","Light Drizzle"),53:("🌦️","Drizzle"),55:("🌧️","Heavy Drizzle"),
    61:("🌧️","Light Rain"),63:("🌧️","Rain"),65:("🌧️","Heavy Rain"),
    71:("🌨️","Light Snow"),73:("🌨️","Snow"),75:("❄️","Heavy Snow"),
    80:("🌦️","Rain Showers"),81:("🌧️","Heavy Showers"),95:("⛈️","Thunderstorm"),
}

@app.route("/weather")
def get_weather():
    try:
        lat  = request.args.get("lat","17.3850")   # default Hyderabad IST
        lon  = request.args.get("lon","78.4867")
        city = request.args.get("city","Hyderabad")

        res = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude":              lat,
                "longitude":             lon,
                "current_weather":       "true",
                "hourly":                "relativehumidity_2m",
                "timezone":              "Asia/Kolkata",
                "forecast_days":         1,
            },
            timeout=8,
        )
        if res.status_code != 200:
            return jsonify({"error":"Weather service unavailable"}), 503

        cw      = res.json().get("current_weather",{})
        code    = cw.get("weathercode",0)
        emoji, desc = WEATHER_CODES.get(code,("🌡️","Unknown"))
        dc      = get_date_context()

        return jsonify({
            "city":        city,
            "temperature": f"{cw.get('temperature','N/A')}°C",
            "description": desc,
            "emoji":       emoji,
            "windspeed":   f"{cw.get('windspeed','N/A')} km/h",
            "date":        dc["full_date"],
            "time":        dc["time"],
        })
    except Exception as e:
        print(f"Weather error: {e}")
        return jsonify({"error":str(e)}), 500

# ════════════════════════════════════════
# V6: NEWS DIGEST ROUTE — Categorized RSS
# ════════════════════════════════════════
NEWS_CATEGORIES = {
    "sports":  "India cricket IPL football sports",
    "tech":    "India technology AI startup software",
    "general": "India news today",
    "local":   "Andhra Pradesh Telangana news",
    "world":   "world news India international",
    "biz":     "India business economy market stocks",
}

@app.route("/news")
def get_news():
    dc       = get_date_context()
    category = request.args.get("category","general")
    base_q   = NEWS_CATEGORIES.get(category, "India news today")
    query    = f"{base_q} {dc['month_year']}"

    try:
        results   = fetch_google_news_rss(query, max_items=8)
        cards = []
        for r in results:
            if len(r.get("title","")) < 10:
                continue
            summary = r.get("summary","")
            if len(summary) > 130:
                summary = summary[:127] + "..."
            cards.append({
                "title":     r["title"],
                "summary":   summary,
                "source":    r.get("source","News"),
                "published": r.get("published",""),
                "url":       r.get("url",""),
                "category":  category,
            })
        return app.response_class(
            response=json.dumps({"cards":cards[:6],"category":category,"date":dc["date"]},ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"News error: {e}")
        return app.response_class(
            response=json.dumps({"cards":[],"category":category,"date":dc["date"]},ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )

# ════════════════════════════════════════
# V6: MUSIC GENERATION — HF MusicGen
# ════════════════════════════════════════
@app.route("/generate-music", methods=["POST"])
def generate_music():
    try:
        data   = request.get_json(force=True)
        prompt = data.get("prompt","calm relaxing Indian music").strip()
        if not prompt:
            return jsonify({"error":"Prompt required"}), 400

        print(f"MusicGen: '{prompt}'")

        headers = {"Content-Type":"application/json"}
        if HF_TOKEN:
            headers["Authorization"] = f"Bearer {HF_TOKEN}"

        res = requests.post(
            "https://api-inference.huggingface.co/models/facebook/musicgen-small",
            headers=headers,
            json={"inputs":prompt,"parameters":{"max_new_tokens":256}},
            timeout=60,
        )
        if res.status_code == 200:
            import base64
            audio_b64 = base64.b64encode(res.content).decode("utf-8")
            return jsonify({
                "audio_base64": audio_b64,
                "format":       "audio/wav",
                "prompt":       prompt,
            })
        elif res.status_code == 503:
            return jsonify({"error":"Model loading, retry in 20 seconds"}), 503
        else:
            return jsonify({"error":f"Generation failed: {res.status_code}"}), 500

    except Exception as e:
        print(f"Music error: {e}")
        return jsonify({"error":str(e)}), 500

# ════════════════════════════════════════
# EXISTING ROUTES (V5.1 unchanged)
# ════════════════════════════════════════
@app.route("/")
def index(): return send_from_directory(".", "index.html")

@app.route("/script.js")
def serve_script(): return send_from_directory(".", "script.js")

@app.route("/favicon.ico")
def favicon(): return "", 204

@app.route("/.well-known/<path:path>")
def well_known(path): return "", 204

@app.route("/health")
def health():
    dc  = get_date_context()
    mem = load_memory()
    return jsonify({
        "status":      "ok",
        "version":     "6.0",
        "date_ist":    dc["full_date"],
        "time_ist":    dc["time"],
        "groq_keys":   len(GROQ_KEYS),
        "temperature": 0.4,
        "memory_keys": len(mem),
        "cache_items": len(_cache),
        "features":    ["weather","news-digest","music-gen","file-upload","memory","tasks"],
    }), 200

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if "files" not in request.files:
            return jsonify({"error":"No files uploaded"}), 400
        files      = request.files.getlist("files")
        question   = request.form.get("question","Summarize this file").strip()
        session_id = request.form.get("session_id","default")

        saved_files = []
        for f in files:
            if f and allowed_file(f.filename):
                safe_name = re.sub(r'[^\w\.\-]','_',f.filename)
                save_path = os.path.join(UPLOAD_DIR,"documents",safe_name)
                f.save(save_path)
                saved_files.append((save_path,f.filename))

        if not saved_files:
            return jsonify({"error":"No valid files"}), 400

        if len(saved_files)==1:
            file_path,filename = saved_files[0]
            file_context,ftype = process_file(file_path,filename)
        else:
            file_context = process_mixed_files(saved_files,question)
            ftype        = "Multiple Files"

        if not file_context or file_context.startswith("[Error"):
            return jsonify({"error":f"Extraction failed: {file_context}"}), 400

        dc         = get_date_context()
        memory_ctx = get_memory_context()

        live_search_ctx = ""
        if needs_search(question):
            try:
                live_search_ctx = search(question)
                if live_search_ctx: set_cache(question,live_search_ctx)
            except Exception as se:
                print(f"Upload search: {se}")

        context_parts = [f"=== {ftype} FILE CONTENT ===\n{file_context}"]
        if live_search_ctx:
            context_parts.append(f"=== CURRENT KNOWLEDGE — {dc['month_year']} ===\n{live_search_ctx}")

        memory_section = f"\n\n{memory_ctx}" if memory_ctx else ""
        system_content = (
            f"You are Panda AI, fully up to date as of {dc['full_date']} IST.{memory_section}\n\n"
            "You have the uploaded file AND current knowledge. Answer directly."
        )
        prompt = (
            f"[{dc['anchor']}]\n\nUser: {question}\n\n"
            + "\n\n".join(context_parts)
        )
        reply = ask_ai([{"role":"system","content":system_content},{"role":"user","content":prompt}])

        for fp,_ in saved_files:
            try: os.remove(fp)
            except: pass

        return app.response_class(
            response=json.dumps({"reply":reply,"file_type":ftype,"session_id":session_id,"searched":bool(live_search_ctx)},ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({"error":str(e)}), 500

@app.route("/memory", methods=["GET"])
def get_memory_route(): return jsonify({"memory":load_memory()})

@app.route("/memory/clear", methods=["POST"])
def clear_mem():
    clear_memory(); return jsonify({"status":"cleared"})

TASKS_FILE = "tasks.json"

def load_tasks():
    try:
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE) as f: return json.load(f)
    except: pass
    return []

def save_tasks(tasks):
    with open(TASKS_FILE,'w') as f: json.dump(tasks,f,ensure_ascii=False,indent=2)

@app.route("/tasks", methods=["GET"])
def get_tasks(): return jsonify({"tasks":load_tasks()})

@app.route("/tasks", methods=["POST"])
def add_task():
    try:
        data = request.get_json(force=True)
        task_name = data.get("task","").strip()
        remind_at = data.get("remind_at","")
        if not task_name: return jsonify({"error":"Task name required"}),400
        tasks = load_tasks()
        tasks.append({"id":len(tasks)+1,"task":task_name,"remind_at":remind_at,"done":False,"created":datetime.now(IST).isoformat()})
        save_tasks(tasks)
        return jsonify({"status":"saved","task":task_name})
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/tasks/due", methods=["GET"])
def due_tasks():
    now = datetime.now(IST).isoformat()
    return jsonify({"tasks":[t for t in load_tasks() if t.get("remind_at","")<=now and not t.get("done",False)]})

@app.route("/tasks/<int:task_id>/done", methods=["POST"])
def mark_done(task_id):
    tasks = load_tasks()
    for t in tasks:
        if t["id"]==task_id: t["done"]=True
    save_tasks(tasks); return jsonify({"status":"done"})

@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    save_tasks([t for t in load_tasks() if t["id"]!=task_id])
    return jsonify({"status":"deleted"})

# ── MAIN CHAT (V5.1 logic unchanged) ──
@app.route("/chat", methods=["POST"])
def chat():
    try:
        body             = request.get_json(force=True)
        user_message     = body.get("message","").strip()
        lang_instruction = body.get("lang_instruction","").strip()
        session_id       = body.get("session_id","default")

        if not user_message:
            return jsonify({"error":"Empty message"}), 400

        dc = get_date_context()
        extract_and_save_memory(user_message)
        memory_ctx = get_memory_context()

        search_context   = ""
        search_attempted = False

        if needs_search(user_message):
            search_attempted = True
            search_context   = get_cache(user_message) or ""
            if not search_context:
                try:
                    search_context = search(user_message)
                    if search_context: set_cache(user_message, search_context)
                except Exception as se:
                    print(f"Search failed: {se}")

        system_content = build_system_prompt(
            dc, memory_ctx,
            has_search=bool(search_context),
            search_attempted=search_attempted
        )
        prompt = build_chat_prompt(user_message, search_context, dc, lang_instruction)

        if session_id not in chat_histories:
            chat_histories[session_id] = []

        messages = (
            [{"role":"system","content":system_content}]
            + chat_histories[session_id][-6:]
            + [{"role":"user","content":prompt}]
        )

        reply = ask_ai(messages, temperature=0.4)

        chat_histories[session_id].append({"role":"user",      "content":user_message})
        chat_histories[session_id].append({"role":"assistant", "content":reply})
        if len(chat_histories[session_id]) > 20:
            chat_histories[session_id] = chat_histories[session_id][-20:]

        return app.response_class(
            response=json.dumps({"reply":reply,"session_id":session_id,"searched":bool(search_context)},ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )

    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({"error":str(e)}), 500

@app.route("/reset", methods=["POST"])
def reset():
    try:
        body = request.get_json(force=True)
        sid  = body.get("session_id","default")
        if sid in chat_histories: del chat_histories[sid]
        return jsonify({"status":"reset"})
    except Exception as e:
        return jsonify({"error":str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    dc   = get_date_context()
    print(f"🐼 Panda AI V6 — Production Build")
    print(f"   IST Date: {dc['full_date']} | Time: {dc['time']}")
    print(f"   Groq: {len(GROQ_KEYS)} keys | Temp: 0.4 | Memory: {len(load_memory())} keys")
    print(f"   Routes: /weather /news /generate-music /chat /upload /tasks /memory")
    app.run(debug=False, host="0.0.0.0", port=port)