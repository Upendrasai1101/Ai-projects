# --- FILE: app.py --- V5 Final
"""
app.py — Panda AI V5
Fixes:
  - File upload now merges with live search for 95% accuracy
  - Scheduled tasks UI support
  - Memory auto-save
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
import os, requests, json, re, random, time, hashlib

from search_tool    import search, fetch_google_news_rss, expand_query
from file_processor import process_file, process_mixed_files, allowed_file, UPLOAD_DIR
from memory         import load_memory, get_memory_context, extract_and_save_memory, clear_memory

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
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
    print("WARNING: No Groq API keys!")
else:
    print(f"✅ Groq keys: {len(GROQ_KEYS)}")

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
            return _cache[k]["context"]
        del _cache[k]
    return None

def set_cache(q, ctx):
    _cache[cache_key(q)] = {"context": ctx, "ts": time.time()}

def get_date_context():
    n = datetime.now()
    return {
        "date":   n.strftime("%B %d, %Y"),
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
        "today","latest","current","now","news","score","result",
        "winner","minister","cm","pm","president","election","live",
        "update","recent","ipl","cricket","price","weather","who is",
        "captain","rank","chief","2026","2025","this year","this month",
        "yesterday","tomorrow","match","standing","stock","rate",
        "vs","versus","win","lose","andhra","telangana","india","world",
        "government","launch","release","announce","died","appointed",
        "elected","arrested","war","attack",
    ]
    return any(kw in q for kw in live_kw)

# ── Groq ──
def ask_groq(messages):
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
                json={"model": GROQ_MODEL, "messages": messages, "max_tokens": 1024, "temperature": 0.2},
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=30,
            )
            if res.status_code == 429:
                print(f"Groq 429 key={label}")
                time.sleep(1.5)
                continue
            if res.status_code in (401, 403):
                continue
            if res.status_code >= 500:
                continue
            data = res.json()
            if "choices" not in data:
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
            "Content-Type": "application/json",
            "HTTP-Referer": "https://huggingface.co/spaces",
            "X-Title": "Panda AI"
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
        print(f"Groq failed: {e} → OpenRouter")
    try:
        reply = ask_openrouter(messages)
        print("OpenRouter ✅")
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
        "status": "ok", "version": "5.0-final",
        "date": dc["date"], "groq_keys": len(GROQ_KEYS),
        "cache_items": len(_cache),
    }), 200

@app.route("/news")
def get_news():
    dc = get_date_context()
    try:
        results   = fetch_google_news_rss(f"India top news {dc['month']}", max_items=6)
        headlines = [r["title"] for r in results if len(r.get("title","")) > 10]
        return app.response_class(
            response=json.dumps({"news": headlines[:5], "date": dc["date"]}, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        return app.response_class(
            response=json.dumps({"news": [], "date": dc["date"]}, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )

# ══════════════════════════════════════════════════
# V5 FIX: File Upload — merges PDF + Live Search
# ══════════════════════════════════════════════════
@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if "files" not in request.files:
            return jsonify({"error": "No files uploaded"}), 400

        files      = request.files.getlist("files")
        question   = request.form.get("question", "Summarize this file").strip()
        session_id = request.form.get("session_id", "default")

        if not files:
            return jsonify({"error": "No files selected"}), 400

        saved_files = []
        for f in files:
            if f and allowed_file(f.filename):
                safe_name = re.sub(r'[^\w\.\-]', '_', f.filename)
                save_path = os.path.join(UPLOAD_DIR, "documents", safe_name)
                f.save(save_path)
                saved_files.append((save_path, f.filename))
                print(f"Saved: {save_path}")

        if not saved_files:
            return jsonify({"error": "No valid files. Supported: PDF, DOCX, XLSX, PPTX, JPG, PNG, MP3, MP4"}), 400

        # Extract file content
        if len(saved_files) == 1:
            file_path, filename = saved_files[0]
            file_context, ftype = process_file(file_path, filename)
        else:
            file_context = process_mixed_files(saved_files, question)
            ftype        = "Multiple Files"

        if not file_context or file_context.startswith("[Error"):
            return jsonify({"error": f"Could not extract text: {file_context}"}), 400

        dc         = get_date_context()
        memory_ctx = get_memory_context()

        # ── ISSUE 2 FIX: Also run live search for current affairs questions ──
        live_search_ctx = ""
        if needs_search(question):
            try:
                print(f"File upload + live search for: {question}")
                live_search_ctx = search(question)
                if live_search_ctx:
                    set_cache(question, live_search_ctx)
            except Exception as se:
                print(f"Live search in upload (non-fatal): {se}")

        # Build merged context
        context_parts = [f"=== {ftype} FILE CONTENT ===\n{file_context}"]
        if live_search_ctx:
            context_parts.append(f"=== LIVE WEB SEARCH (for current data) ===\n{live_search_ctx}")

        merged_context = "\n\n".join(context_parts)
        memory_section = f"\n\n{memory_ctx}" if memory_ctx else ""

        system_content = (
            f"You are Panda AI — a multimodal AI analyst. {dc['anchor']}{memory_section}\n\n"
            "You have TWO sources of information:\n"
            "1. FILE CONTENT — extracted from the uploaded file\n"
            "2. LIVE WEB SEARCH — current data from the internet (if available)\n\n"
            "RULES:\n"
            "- For questions about the FILE → use FILE CONTENT\n"
            "- For current affairs questions (CM, PM, scores, news) → use LIVE WEB SEARCH\n"
            "- NEVER say 'knowledge cutoff' if live search data is provided\n"
            "- Combine both sources intelligently\n"
            "- Be accurate, concise, and friendly"
        )
        prompt = (
            f"DATE: {dc['anchor']}\n\n"
            f"USER QUESTION: {question}\n\n"
            f"{merged_context}\n\n"
            f"Answer using the most relevant source above."
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user",   "content": prompt}
        ]
        reply = ask_ai(messages)

        # Cleanup temp files
        for file_path, _ in saved_files:
            try: os.remove(file_path)
            except: pass

        return app.response_class(
            response=json.dumps({
                "reply": reply, "file_type": ftype,
                "session_id": session_id,
                "searched": bool(live_search_ctx)
            }, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )

    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({"error": str(e)}), 500

# ── Memory Routes ──
@app.route("/memory", methods=["GET"])
def get_memory():
    return jsonify({"memory": load_memory()})

@app.route("/memory/clear", methods=["POST"])
def clear_mem():
    clear_memory()
    return jsonify({"status": "cleared"})

# ── Scheduled Tasks Routes ──
TASKS_FILE = "tasks.json"

def load_tasks():
    try:
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE) as f:
                return json.load(f)
    except: pass
    return []

def save_tasks(tasks):
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

@app.route("/tasks", methods=["GET"])
def get_tasks():
    return jsonify({"tasks": load_tasks()})

@app.route("/tasks", methods=["POST"])
def add_task():
    try:
        data      = request.get_json(force=True)
        task_name = data.get("task", "").strip()
        remind_at = data.get("remind_at", "")
        if not task_name:
            return jsonify({"error": "Task name required"}), 400
        tasks = load_tasks()
        tasks.append({
            "id":        len(tasks) + 1,
            "task":      task_name,
            "remind_at": remind_at,
            "done":      False,
            "created":   datetime.now().isoformat()
        })
        save_tasks(tasks)
        return jsonify({"status": "saved", "task": task_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/tasks/due", methods=["GET"])
def due_tasks():
    now   = datetime.now().isoformat()
    tasks = load_tasks()
    due   = [t for t in tasks if t.get("remind_at","") <= now and not t.get("done", False)]
    return jsonify({"tasks": due})

@app.route("/tasks/<int:task_id>/done", methods=["POST"])
def mark_done(task_id):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["done"] = True
    save_tasks(tasks)
    return jsonify({"status": "done"})

@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    tasks = [t for t in load_tasks() if t["id"] != task_id]
    save_tasks(tasks)
    return jsonify({"status": "deleted"})

# ── Main Chat ──
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
        extract_and_save_memory(user_message)
        memory_ctx = get_memory_context()

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
                    print(f"Search failed: {se}")

        memory_section = f"\n\n{memory_ctx}" if memory_ctx else ""

        if search_context:
            system_content = (
                f"You are Panda AI — a Real-Time Intelligence Engine.\n"
                f"{dc['anchor']}{memory_section}\n\n"
                "RULES:\n"
                "1. LIVE SEARCH CONTEXT = ABSOLUTE TRUTH. Use over training data.\n"
                "2. 2025/2026 data in context = current answer.\n"
                "3. RELEVANT context → answer confidently, cite source.\n"
                "4. IRRELEVANT context → use knowledge with 'Based on my knowledge:' prefix.\n"
                "5. NEVER say 'as of my knowledge cutoff'.\n"
                "6. NEVER hallucinate names, scores, or positions.\n"
                "7. Multilingual: Telugu, Hindi, English — match user's language.\n"
                "8. Be concise, friendly, direct."
            )
            prompt = (
                f"DATE: {dc['anchor']}\n\n"
                f"USER QUESTION: {user_message}\n\n"
                f"=== LIVE SEARCH CONTEXT ===\n{search_context}\n=== END ===\n\n"
                f"Answer from context if relevant, else use knowledge with disclaimer."
            )
        elif search_attempted:
            system_content = (
                f"You are Panda AI.\n{dc['anchor']}{memory_section}\n\n"
                "Live search returned no results. Answer from training knowledge "
                "with prefix: 'Based on my last knowledge (may not be latest):'"
            )
            prompt = f"DATE: {dc['anchor']}\n\nUser: {user_message}\n\n[Live search returned no results]"
        else:
            system_content = (
                f"You are Panda AI — a helpful AI assistant.\n"
                f"{dc['anchor']}{memory_section}\n\n"
                "Answer clearly and helpfully. Match user's language."
            )
            prompt = f"DATE: {dc['anchor']}\n\nUser: {user_message}"

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
                "reply": reply, "session_id": session_id,
                "searched": bool(search_context),
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
    print(f"🐼 Panda AI V5 Final — http://0.0.0.0:{port}")
    print(f"   Groq: {len(GROQ_KEYS)} keys | OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}")
    app.run(debug=False, host="0.0.0.0", port=port)