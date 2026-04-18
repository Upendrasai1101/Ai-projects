# --- FILE: app.py --- V5.1 Real-Time Persona Build
"""
Panda AI V5.1 — Real-Time Persona Build
Core Identity: AI always knows TODAY's actual date (dynamic via datetime).
No hardcoded dates. No cutoff excuses. No 'I don't have real-time access'.
- Date auto-updates every day via Python datetime — no code changes needed
- LIVE SEARCH context = AI's own current knowledge
- Snippets = first-hand information, answered authoritatively
- Universal: politics, sports, greetings, general knowledge — all in-character
- temperature=0.4, top_p=0.9
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
import os, requests, json, re, random, time, hashlib

from search_tool    import search, fetch_google_news_rss, is_time_sensitive
from file_processor import process_file, process_mixed_files, allowed_file, UPLOAD_DIR
from memory         import load_memory, get_memory_context, extract_and_save_memory, clear_memory

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
CORS(app)
app.config['JSON_AS_ASCII'] = False

# ── Groq Keys ──
GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
]
GROQ_KEYS = [k for k in GROQ_KEYS if k]
print(f"✅ Groq keys loaded: {len(GROQ_KEYS)} key(s)")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_MODEL         = "llama-3.3-70b-versatile"

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

def get_date_context():
    """
    Fully dynamic — no hardcoded dates anywhere.
    Called fresh on every request so it always returns today.
    """
    n = datetime.now()
    return {
        "date":       n.strftime("%B %d, %Y"),      # e.g. April 18, 2026
        "year":       str(n.year),                    # e.g. 2026
        "month":      n.strftime("%B"),              # e.g. April
        "month_year": n.strftime("%B %Y"),          # e.g. April 2026
        "day":        n.strftime("%A"),              # e.g. Saturday
        "full_date":  n.strftime("%A, %B %d, %Y"), # e.g. Saturday, April 18, 2026
        "anchor":     f"Today: {n.strftime('%A, %B %d, %Y')}",
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

# ── Groq ──
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

# ════════════════════════════════════════════════════════════════
# SYSTEM PROMPT — Dynamic Real-Time Persona
#
# Core design decisions:
# 1. AI self-identifies as living on TODAY's actual date — fully dynamic, no hardcoding
# 2. Live search context = AI's own knowledge, not "external results"
# 3. Forbidden phrases list baked into identity, not rules
# 4. Universal: greetings, sports, politics, GK all handled in-character
# ════════════════════════════════════════════════════════════════
def build_system_prompt(dc, memory_ctx, has_search, search_attempted):
    memory_section = f"\n\n{memory_ctx}" if memory_ctx else ""

    # ── CORE IDENTITY (same for all modes) ──
    # This block is always injected — establishes the persona
    identity = (
        # ── Dynamic date: auto-updates every day, zero hardcoding ──
        f"You are Panda AI, a smart and friendly AI assistant.\n"
        f"Today is {dc['full_date']}.\n"
        f"You are fully aware of current events, sports, politics, and general knowledge\n"
        f"as of {dc['day']}, {dc['month_year']}.\n\n"

        # Forbidden phrases — framed as identity, not rules
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

        "INSTEAD, speak with today's date naturally:\n"
        f"  ✅ 'As of {dc['full_date']}, X is Y.'\n"
        f"  ✅ 'Today is {dc['full_date']}. The current [role] is X.'\n"
        "  ✅ 'Based on the latest information, X happened.'\n"
        "  ✅ 'X won the match yesterday.'\n"
        f"{memory_section}"
    )

    if has_search:
        return (
            identity +
            "\n\n━━━ HOW YOUR KNOWLEDGE WORKS ━━━\n"
            "When you respond, you have access to current news and information.\n"
            "The information marked [LIVE SEARCH] below is YOUR OWN CURRENT KNOWLEDGE —\n"
            "it is not an external search result you are reading. It is what you know right now.\n"
            "Speak from it naturally and authoritatively, as if you always knew this.\n\n"

            "HOW TO USE IT:\n"
            "• Treat every headline and snippet as a verified fact you are aware of.\n"
            "• If a snippet says 'X won' → you know X won. Say it directly.\n"
            "• If a snippet shows a person in a leadership role → you know their role. State it.\n"
            "• Combine related snippets naturally to form a complete, flowing answer.\n"
            "• News from the last 48 hours = current knowledge for 'today'/'yesterday' questions.\n\n"

            "RESPONSE STYLE:\n"
            "• Answer directly, like a knowledgeable friend who follows the news.\n"
            "• No need to cite 'according to search results' — just state the facts naturally.\n"
            "• If snippets give partial info → fill the answer naturally: "
            "'X won the match against Y, securing their spot in the standings.'\n"
            "• If truly nothing in context matches → answer from your general knowledge confidently.\n\n"

            "LANGUAGE & TONE:\n"
            "• Match the user's language: Telugu, Hindi, or English.\n"
            "• Be warm, conversational, and direct. No jargon. No unnecessary hedging."
        )

    elif search_attempted:
        # Search ran but returned nothing — still stay in-character
        return (
            identity +
            "\n\n━━━ KNOWLEDGE NOTE ━━━\n"
            "Your real-time feed did not return specific results for this query.\n"
            "Answer from your general knowledge confidently.\n"
            "For very recent events (last few days), you can say:\n"
            "  'I don't have the very latest update on this, but as of recently...'\n"
            "Never mention cutoff dates or training limitations.\n"
            "Match language: Telugu, Hindi, or English."
        )

    else:
        # No search needed (greetings, general knowledge, coding etc.)
        return (
            identity +
            "\n\n━━━ RESPONSE STYLE ━━━\n"
            "Answer naturally and helpfully from your knowledge.\n"
            "For greetings → be warm and friendly.\n"
            "For general knowledge → answer confidently.\n"
            "For coding/technical → be precise and helpful.\n"
            "Match language: Telugu, Hindi, or English."
        )

# ════════════════════════════════════════
# PROMPT BUILDER
# Context injected as "AI's own knowledge"
# not as "search results"
# ════════════════════════════════════════
def build_chat_prompt(user_message, search_context, dc, lang_instruction=""):
    if search_context:
        prompt = (
            f"[{dc['anchor']}]\n\n"
            f"User: {user_message}\n\n"
            # Framed as AI's knowledge, not external search
            f"[YOUR CURRENT KNOWLEDGE — {dc['month_year']}]\n"
            f"{search_context}\n"
            f"[END]\n\n"
            f"Answer naturally and directly using your current knowledge above.\n"
            f"Speak authoritatively — this is what you know right now."
        )
    else:
        prompt = (
            f"[{dc['anchor']}]\n\n"
            f"User: {user_message}"
        )

    if lang_instruction:
        prompt += f"\n\n[Respond in: {lang_instruction}]"

    return prompt

# ════════════════════════════════════════
# ROUTES
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
        "version":     "5.0-persona",
        "date":        dc["date"],
        "groq_keys":   len(GROQ_KEYS),
        "temperature": 0.4,
        "top_p":       0.9,
        "memory_keys": len(mem),
        "cache_items": len(_cache),
        "mode":        "Dynamic Real-Time Persona (date auto-updates)",
    }), 200

@app.route("/news")
def get_news():
    dc = get_date_context()
    try:
        results   = fetch_google_news_rss(f"India top news {dc['month_year']}", max_items=6)
        headlines = [r["title"] for r in results if len(r.get("title","")) > 10]
        return app.response_class(
            response=json.dumps({"news":headlines[:5],"date":dc["date"]},ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"News error: {e}")
        return app.response_class(
            response=json.dumps({"news":[],"date":dc["date"]},ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )

# ── File Upload ──
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
            return jsonify({"error":"No valid files. Supported: PDF, DOCX, XLSX, PPTX, JPG, PNG, MP3, MP4"}),400

        if len(saved_files)==1:
            file_path,filename = saved_files[0]
            file_context,ftype = process_file(file_path,filename)
        else:
            file_context = process_mixed_files(saved_files,question)
            ftype        = "Multiple Files"

        if not file_context or file_context.startswith("[Error"):
            return jsonify({"error":f"Extraction failed: {file_context}"}),400

        dc         = get_date_context()
        memory_ctx = get_memory_context()

        live_search_ctx = ""
        if needs_search(question):
            try:
                live_search_ctx = search(question)
                if live_search_ctx: set_cache(question,live_search_ctx)
            except Exception as se:
                print(f"Live search in upload: {se}")

        context_parts  = [f"=== {ftype} FILE CONTENT ===\n{file_context}"]
        if live_search_ctx:
            context_parts.append(f"=== CURRENT KNOWLEDGE — {dc['month_year']} ===\n{live_search_ctx}")

        memory_section = f"\n\n{memory_ctx}" if memory_ctx else ""
        system_content = (
            f"You are Panda AI, fully up to date as of {dc['date']}.{memory_section}\n\n"
            "You have access to the uploaded file AND current news knowledge.\n"
            "Answer directly from both. Never mention knowledge cutoffs or training limitations.\n"
            "Be helpful, accurate, and confident."
        )
        prompt = (
            f"[{dc['anchor']}]\n\nUser question: {question}\n\n"
            + "\n\n".join(context_parts)
            + "\n\nAnswer directly and helpfully."
        )
        messages = [{"role":"system","content":system_content},{"role":"user","content":prompt}]
        reply    = ask_ai(messages, temperature=0.4)

        for file_path,_ in saved_files:
            try: os.remove(file_path)
            except: pass

        return app.response_class(
            response=json.dumps({"reply":reply,"file_type":ftype,"session_id":session_id,"searched":bool(live_search_ctx)},ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({"error":str(e)}),500

# ── Memory ──
@app.route("/memory", methods=["GET"])
def get_memory(): return jsonify({"memory":load_memory()})

@app.route("/memory/clear", methods=["POST"])
def clear_mem():
    clear_memory(); return jsonify({"status":"cleared"})

# ── Tasks ──
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
        tasks.append({"id":len(tasks)+1,"task":task_name,"remind_at":remind_at,"done":False,"created":datetime.now().isoformat()})
        save_tasks(tasks)
        return jsonify({"status":"saved","task":task_name})
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/tasks/due", methods=["GET"])
def due_tasks():
    now = datetime.now().isoformat()
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

# ════════════════════════════════════════
# MAIN CHAT
# ════════════════════════════════════════
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

        # Auto memory — silent
        extract_and_save_memory(user_message)
        memory_ctx = get_memory_context()

        # Live search
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

        # Build prompts
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
        print(f"Reply: {len(reply)} chars")

        # Update history
        chat_histories[session_id].append({"role":"user",      "content":user_message})
        chat_histories[session_id].append({"role":"assistant", "content":reply})
        if len(chat_histories[session_id]) > 20:
            chat_histories[session_id] = chat_histories[session_id][-20:]

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
    print(f"🐼 Panda AI V5 — Real-Time Persona Build")
    print(f"   Identity: {dc["full_date"]} | Temp: 0.4 | Memory: {len(load_memory())} keys")
    print(f"   Date: fully dynamic (auto-updates daily) | No cutoff phrases")
    app.run(debug=False, host="0.0.0.0", port=port)