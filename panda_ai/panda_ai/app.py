# ==================================================================================
# @workspace: PANDA AI V8.3 - DYNAMIC MULTI-USER ARCHITECTURE OPTIMIZATION
# ----------------------------------------------------------------------------------
# [STRATEGY] Converting Static 'Upendrasai' profile to Dynamic Session-Based Shards.
# [INDEXING] Re-evaluating all project modules for cross-functional integration.
# ----------------------------------------------------------------------------------
# [COMPONENTS ANALYSIS]:
# - APP.PY: Main Hub - Integrating Flask Sessions & UUID tracking for isolation.
# - USER_PROFILE.PY: Logic Layer - Handling 'user_memories/' directory and Welcome Modals.
# - MEMORY.PY: Intelligence Layer - Shifting from Regex to LLM Entity Extraction.
# - SEARCH_TOOL.PY: Verification Layer - Implementation of 'extract_sources()'.
# ==================================================================================

from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime, timedelta, date
import pytz
import os, requests, json, re, random, time, hashlib, base64, threading

from search_tool    import get_web_search, is_time_sensitive, detects_future_intent, get_upcoming_dates, extract_sources
from file_processor import process_file, process_mixed_files, allowed_file, UPLOAD_DIR
from memory         import load_memory, get_memory_context, extract_and_save_memory, clear_memory
from media_generator import generate_image, generate_video, generate_audio
from user_profile   import (get_user_profile, save_user_profile,
                           is_new_user, get_memory_context as get_profile_context)

load_dotenv()

# ── Debug: confirm all keys present at startup ──
print(f"DEBUG: CF_ACCOUNT_1  = {'✅' if os.getenv('CF_ACCOUNT_ID_1')  else '❌'}")
print(f"DEBUG: CF_TOKEN_1    = {'✅' if os.getenv('CF_API_TOKEN_1')   else '❌'}")
print(f"DEBUG: CF_ACCOUNT_2  = {'✅' if os.getenv('CF_ACCOUNT_ID_2')  else '❌'}")
print(f"DEBUG: CF_TOKEN_2    = {'✅' if os.getenv('CF_API_TOKEN_2')   else '❌'}")
print(f"DEBUG: UNSPLASH      = {'✅' if os.getenv('UNSPLASH_ACCESS_KEY') else '❌'}")
print(f"DEBUG: PEXELS        = {'✅' if os.getenv('PEXELS_API_KEY')   else '❌'}")
print(f"DEBUG: AUDIO ENGINE  = ✅ CDN Library (no API key needed)")
# V8.2: HF_TOKEN for image captioning
print(f"DEBUG: HF_TOKEN      = {'✅' if os.getenv('HF_TOKEN') else '❌ (image captioning disabled)'}")

app = Flask(__name__, static_folder=".", static_url_path="")
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
CORS(app)
app.config['JSON_AS_ASCII'] = False
app.secret_key = os.getenv("SECRET_KEY", "panda-v8-secret-change-me")

@app.route('/static/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(os.path.join(app.root_path, 'static', 'audio'), filename)

# ── V8.4: Register module blueprints ──────────────────────────
from modules.mail.mail_routes   import mail_bp
from modules.pad.pad_routes     import pad_bp
from modules.study.study_routes import study_bp

app.register_blueprint(mail_bp,  url_prefix="/mail")
app.register_blueprint(pad_bp,   url_prefix="/pad")
app.register_blueprint(study_bp, url_prefix="/study")
# ──────────────────────────────────────────────────────────────

# ── V8.5: Register widget handler blueprints ──────────────────
from maps_handler   import maps_bp
from charts_handler import charts_bp
from canvas_handler import canvas_bp

app.register_blueprint(maps_bp,   url_prefix="/maps")
app.register_blueprint(charts_bp, url_prefix="/charts")
app.register_blueprint(canvas_bp, url_prefix="/canvas")

from orator_handler import orator_bp
app.register_blueprint(orator_bp, url_prefix="/orator")
# ──────────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════
# CORE KEYS  (UNCHANGED from V8.1)
# ══════════════════════════════════════════════════════════════
GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3"),
    os.getenv("GROQ_API_KEY_4"),
    os.getenv("GROQ_API_KEY_5"),
    os.getenv("GROQ_API_KEY_6"),
    os.getenv("GROQ_API_KEY_7"),
    os.getenv("GROQ_API_KEY_8"),
]
GROQ_KEYS = [k for k in GROQ_KEYS if k is not None]
print(f"✅ Groq keys loaded: {len(GROQ_KEYS)} key(s)")

# ── V8.2: Keep Groq key availability for audio/video transcription ──────
# The chat rotation pool (GROQ_KEYS) is unaffected — chat still rotates normally.
if GROQ_KEYS:
    print(f"✅ file_processor: Groq key pool ready ({len(GROQ_KEYS)} key(s))")
else:
    print("⚠️  file_processor: No Groq key — audio/video transcription disabled")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_MODEL         = "openai/gpt-oss-20b"

PEXELS_API_KEY      = os.getenv("PEXELS_API_KEY",      "")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
HF_TOKEN            = os.getenv("HF_TOKEN", "")  # V8.2: for health reporting

# ══════════════════════════════════════════════════════════════
# IST TIMEZONE  (UNCHANGED)
# ══════════════════════════════════════════════════════════════
IST = pytz.timezone("Asia/Kolkata")

def get_date_context():
    n = datetime.now(IST)
    week_dates = [(n + timedelta(days=i)).strftime("%B %d, %Y") for i in range(8)]
    week_range = f"{week_dates[0]} → {week_dates[-1]}"
    return {
        "date":       n.strftime("%B %d, %Y"),
        "year":       str(n.year),
        "month":      n.strftime("%B"),
        "month_year": n.strftime("%B %Y"),
        "day":        n.strftime("%A"),
        "time":       n.strftime("%I:%M %p IST"),
        "full_date":  n.strftime("%A, %B %d, %Y"),
        "anchor":     f"Today: {n.strftime('%A, %B %d, %Y')} | Time: {n.strftime('%I:%M %p IST')}",
        "week_range":  week_range,
        "week_dates":  week_dates,
    }

# ══════════════════════════════════════════════════════════════
# SESSION-ISOLATED CACHE  (V8.5: Thread-safe, multi-user safe)
# ══════════════════════════════════════════════════════════════

CACHE_TTL = 120
_cache_lock = threading.Lock()  # Thread-safe locking for cache access

def cache_key(q):
    return hashlib.md5(q.lower().strip().encode()).hexdigest()

def compact_search_context(text, max_chars=1800):
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', str(text)).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip() + "\n...[truncated for session storage]"


def get_cache(q):
    """Disabled: chat responses are never reused from session cache."""
    return None


def set_cache(q, ctx):
    """Disabled: chat responses are never stored in session cache."""
    return None

# ══════════════════════════════════════════════════════════════
# SEARCH GATE  (UNCHANGED)
# ══════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════
# GROQ KEY ROTATION  (UNCHANGED)
# ══════════════════════════════════════════════════════════════
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
            "X-Title":"Panda AI V8.2"
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

# ══════════════════════════════════════════════════════════════
# SYSTEM PROMPT  (V8.4: Dynamic Year + Anti-Mixup Protocol)
# ══════════════════════════════════════════════════════════════
def format_search_results(results):
    if not results:
        return ""
    blocks = []
    for i, item in enumerate(results[:8], 1):
        title = (item.get("title") or "").strip()
        summary = (item.get("summary") or "").strip()
        url = (item.get("url") or "").strip()
        published = (item.get("published") or "").strip()
        source = (item.get("source") or "Web").strip()
        if not title:
            continue
        block = f"[{i}. {title} | {source} | {published or 'Live'} | {url}]"
        if summary:
            block += f"\n{summary}"
        blocks.append(block)
    return "\n\n".join(blocks)


def build_system_prompt(dc, memory_ctx, has_search, search_attempted):
    now_ist = datetime.now(IST)
    current_year = now_ist.year
    today_label = now_ist.strftime("%A, %B %d, %Y")
    time_label = now_ist.strftime("%I:%M %p IST")
    
    memory_section = f"\n\n{memory_ctx}" if memory_ctx else ""
    
    identity = (
        f"You are Panda AI V8.4, a smart and friendly AI assistant built in India.\n"
        f"Today is {today_label} | Current IST Time: {time_label}.\n"
        f"You are fully aware of current events, sports, politics, and general knowledge\n"
        f"as of {now_ist.strftime('%A')}, {now_ist.strftime('%B %Y')}.\n"
        f"You are operating in the live calendar year {current_year}.\n\n"
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
        "  ✅ 'Based on the latest information, X happened.'\n\n"
        f"── ANTI-MIXUP PROTOCOL ──\n"
        f"Panda AI is operating in the live calendar year {current_year}.\n"
        f"If historical database snapshots (like Wikipedia) conflict with active {current_year} live news streams\n"
        f"(e.g., outdated officials vs recent budget/policy actors), you MUST:\n"
        f"  1. COMPLETELY DISCARD the old/outdated entities from historical sources\n"
        f"  2. Confidently state the {current_year} reality without any ambiguity\n"
        f"  3. NEVER mix outdated and new names together in your response\n"
        f"  4. Prioritize live news and real-time information over historical snapshots\n"
        f"{memory_section}"
    )
    live_context_rules = (
        "\n\n━━━ HYBRID CONTEXT EVALUATION & FALLBACK POLICY ━━━\n"
        "1. Tier 1 (Live Search Alignment): If the live search context explicitly contains the answer to the user's query, base the response primarily on that live context.\n"
        "2. Tier 2 (Supplementary Background): If the search snippets do not explicitly contain the answer, treat them as supporting background and continue answering from your base knowledge seamlessly.\n"
        "3. Tier 3 (Graceful Fallback Limit): Only mention a limitation when neither the live search context nor your base knowledge contains verifiable information relevant to the query.\n"
        "4. Zero Empty Payload Rule: Never refuse, block, or return an empty response solely because the snippets are incomplete."
    )
    factual_reasoning_rules = (
        "\n\n━━━ FACTUAL REASONING & ENTITY RELATIONS ━━━\n"
        "1. Subject-Predicate Validation: Only pair an Entity with an Attribute if the source text explicitly links them as a permanent or primary relation.\n"
        "2. Context vs Identity: Distinguish between where/how an entity operates (event context) versus what the entity actually is (core identity).\n"
        "3. Query Specificity: Answer strictly with entities that directly satisfy all constraints in the user's prompt, filtering out peripheral entities mentioned in the same search context."
    )
    strict_boundary_rules = (
        "\n\n━━━ STRICT BOUNDARY & RELATION EXTRACTION ━━━\n"
        "1. Entity-Attribute Isolation: Match an attribute to an entity only if the source context explicitly defines a direct identity or ownership relationship.\n"
        "2. Location vs Identity Disambiguation: Do not attribute a geographic or organizational identity to a visiting or external entity simply because they appear in the same event context.\n"
        "3. Strict Constraint Filtering: Output strictly the entities that directly satisfy all criteria of the query. Exclude all cross-referenced or adjacent entities."
    )
    base_prompt = identity + live_context_rules + factual_reasoning_rules + strict_boundary_rules
    widget_instructions = (
        "\n\nWIDGET INSTRUCTIONS:\n"
        "When the user asks about a specific location, place, city, country, or landmark,\n"
        "include this EXACTLY on its own line in your response:\n"
        "SHOW_MAP: <place name or full description>\n\n"
        "When the user asks for statistics, data comparisons, charts, graphs, or numerical analysis,\n"
        "include this EXACTLY on its own line in your response:\n"
        "SHOW_CHART: <description of the data the user asked for>\n\n"
        "For all other questions respond normally with no widget trigger.\n"
        "Never include both SHOW_MAP and SHOW_CHART in the same response.\n"
        "The trigger keyword must be on its own line with no extra text around it."
    )
    if has_search:
        return (
            base_prompt +
            f"\n\n━━━ YOUR CURRENT KNOWLEDGE ━━━\n"
            f"The [LIVE SEARCH] data injected below is YOUR OWN current knowledge.\n"
            f"It is not external data — it is what you know right now in {current_year}.\n"
            "Speak from it naturally and authoritatively.\n\n"
            "HOW TO USE IT:\n"
            "• Headlines and snippets = verified facts you are aware of.\n"
            "• If snippet says 'X won' → you know X won. State it directly.\n"
            "• Person shown doing a role's duties → you know their role.\n"
            "• News from last 48 hours = current for today/yesterday questions.\n"
            "• Combine snippets naturally into a complete, flowing answer.\n"
            "• [REAL-TIME FRESH UPDATE] tags = must prioritize these sources in your response.\n"
            "• [HISTORICAL BACKUP] tags = use only if no live news available for that topic.\n\n"
            "LANGUAGE & TONE:\n"
            "• Match user's language: Telugu, Hindi, or English.\n"
            "• Be warm, direct, and conversational like a knowledgeable friend." +
            widget_instructions
        )
    elif search_attempted:
        return (
            base_prompt +
            "\n\n━━━ KNOWLEDGE NOTE ━━━\n"
            "Real-time feed returned no results for this query.\n"
            "Answer from your general knowledge confidently.\n"
            "For very recent events say: 'I don't have the very latest on this, but recently...'\n"
            "Never mention cutoff dates. Match language: Telugu, Hindi, or English." +
            widget_instructions
        )
    else:
        return (
            base_prompt +
            "\n\n━━━ RESPONSE STYLE ━━━\n"
            "Answer naturally and helpfully.\n"
            "For greetings → warm and friendly.\n"
            "For general knowledge → confident and clear.\n"
            "For coding → precise and helpful.\n"
            "Match language: Telugu, Hindi, or English." +
            widget_instructions
        )

def build_chat_prompt(user_message, search_context, dc, lang_instruction=""):
    if search_context:
        prompt = (
            f"[{dc['anchor']}]\n\n"
            f"User: {user_message}\n\n"
            f"[YOUR CURRENT KNOWLEDGE — {dc['month_year']}]\n"
            f"{search_context}\n"
            f"[END]\n\n"
            f"Use the background information above when it helps, but do not depend on it exclusively.\n"
            f"If the snippets do not explicitly contain the answer, answer naturally from your base knowledge and weave the context in only as support.\n"
            f"Speak authoritatively — this is what you know right now."
        )
    else:
        prompt = f"[{dc['anchor']}]\n\nUser: {user_message}"
    if lang_instruction:
        prompt += f"\n\n[Respond in: {lang_instruction}]"
    return prompt

# ══════════════════════════════════════════════════════════════
# WEATHER  (UNCHANGED)
# ══════════════════════════════════════════════════════════════
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
        lat  = request.args.get("lat","17.3850")
        lon  = request.args.get("lon","78.4867")
        city = request.args.get("city","Hyderabad")
        try:
            res  = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={"latitude":lat,"longitude":lon,"current_weather":"true",
                        "hourly":"relativehumidity_2m","timezone":"Asia/Kolkata","forecast_days":1},
                timeout=15,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.RequestException) as timeout_err:
            print(f"Weather API timeout/network error: {timeout_err}")
            dc = get_date_context()
            return jsonify({
                "city":f"{city} (Offline Mode)",
                "temperature":"--",
                "description":"Offline",
                "emoji":"🌤️",
                "windspeed":"-- km/h",
                "date":dc["full_date"],"time":dc["time"],
                "_fallback":True
            }), 200
        
        if res.status_code != 200:
            dc = get_date_context()
            return jsonify({
                "city":f"{city} (Offline Mode)",
                "temperature":"--",
                "description":"Offline",
                "emoji":"🌤️",
                "windspeed":"-- km/h",
                "date":dc["full_date"],"time":dc["time"],
                "_fallback":True
            }), 200
        cw          = res.json().get("current_weather",{})
        code        = cw.get("weathercode",0)
        emoji, desc = WEATHER_CODES.get(code,("🌡️","Unknown"))
        dc          = get_date_context()
        return jsonify({
            "city":city,"temperature":f"{cw.get('temperature','N/A')}°C",
            "description":desc,"emoji":emoji,
            "windspeed":f"{cw.get('windspeed','N/A')} km/h",
            "date":dc["full_date"],"time":dc["time"],
        }), 200
    except Exception as e:
        print(f"Weather error (fallback): {e}")
        dc = get_date_context()
        return jsonify({
            "city":"Kothagudem (Offline Mode)",
            "temperature":"--",
            "description":"Offline",
            "emoji":"🌤️",
            "windspeed":"-- km/h",
            "date":dc["full_date"],"time":dc["time"],
            "_fallback":True
        }), 200

# ══════════════════════════════════════════════════════════════
# NEWS  (UNCHANGED)
# ══════════════════════════════════════════════════════════════
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
    base_q   = NEWS_CATEGORIES.get(category,"India news today")
    query    = f"{base_q} {dc['month_year']}"
    try:
        results = get_web_search(query)
        cards   = []
        for r in results:
            title = r.get("title", "")
            if len(title) < 10: continue
            summary = r.get("summary", "")
            if len(summary) > 130: summary = summary[:127] + "..."
            cards.append({"title":title,"summary":summary,
                          "source":r.get("source","News"),"published":r.get("published",""),
                          "url":r.get("url",""),"category":category})
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

# ══════════════════════════════════════════════════════════════
# /generate-media  (UNCHANGED)
# ══════════════════════════════════════════════════════════════
@app.route("/generate-media", methods=["POST"])
def generate_media_route():
    try:
        body       = request.get_json(force=True)
        media_type = body.get("type", "image").strip().lower()
        prompt     = body.get("prompt", "").strip()
        if not prompt:
            return jsonify({"error": "Prompt is required."}), 400
        if media_type not in ("image", "audio", "video"):
            return jsonify({"error": "type must be: image, audio, or video"}), 400
        print(f"🎬 Studio [{media_type}]: '{prompt[:60]}'")
        if   media_type == "image": result = generate_image(prompt)
        elif media_type == "video": result = generate_video(prompt)
        elif media_type == "audio": result = generate_audio(prompt)
        if "error" in result:
            return jsonify(result), 500
        return app.response_class(
            response=json.dumps(result, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"Media route error: {e}")
        return jsonify({"error": str(e)}), 500

# ══════════════════════════════════════════════════════════════
# STATIC ROUTES  (UNCHANGED)
# ══════════════════════════════════════════════════════════════
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
    today = date.today()
    return jsonify({
        "status":           "ok",
        "version":          "8.2",
        "date_ist":         dc["full_date"],
        "time_ist":         dc["time"],
        "week_range":       dc["week_range"],
        "groq_keys":        len(GROQ_KEYS),
        "cf_configured":    bool(os.getenv("CF_ACCOUNT_ID_1")),
        "unsplash_set":     bool(UNSPLASH_ACCESS_KEY),
        "pexels_set":       bool(PEXELS_API_KEY),
        "cdn_audio":        "✅ CDN Library (no API key needed)",
        # V8.2: cloud processor status
        "hf_token_set":     bool(HF_TOKEN),
        "image_engine":     "HF BLIP captioning (cloud) ✅" if HF_TOKEN else "⚠️ HF_TOKEN missing",
        "audio_engine":     "Groq distil-whisper-large-v3-en ✅" if GROQ_KEYS else "⚠️ No Groq key",
        "video_engine":     "ffmpeg → Groq Whisper ✅" if GROQ_KEYS else "⚠️ No Groq key",
        "memory_keys":      len(mem),
        "cache_items":      len(session.get('user_cache', {})),  # Session-isolated cache count
        "features":         ["weather","news","generate-media","file-upload","memory","tasks","deep-crawl","future-intelligence"],
        "media_engines":    {"image":"CF-Workers-AI+Unsplash","video":"Pexels","audio":"CDN-Library"},
        # V8.2: Future Intelligence Layer
        "future_intelligence": {
            "enabled": True,
            "today": today.strftime("%B %d, %Y"),
            "upcoming_days": get_upcoming_dates(7),
        },
    }), 200

# ══════════════════════════════════════════════════════════════
# UPLOAD  (UNCHANGED signature — cloud calls now inside file_processor)
# ══════════════════════════════════════════════════════════════
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
        memory_ctx = get_profile_context()  # Use aliased function from user_profile
        live_search_ctx = ""
        if needs_search(question):
            try:
                live_search_results = get_web_search(question)
                live_search_ctx = format_search_results(live_search_results)
                if live_search_ctx: set_cache(question,live_search_ctx)
            except Exception as se:
                print(f"Upload search: {se}")
        context_parts = [f"=== {ftype} FILE CONTENT ===\n{file_context}"]
        if live_search_ctx:
            context_parts.append(f"=== CURRENT KNOWLEDGE — {dc['month_year']} ===\n{live_search_ctx}")
        memory_section = f"\n\n{memory_ctx}" if memory_ctx else ""
        system_content = (
            f"You are Panda AI V8.2, fully up to date as of {dc['full_date']} IST.{memory_section}\n\n"
            "You have the uploaded file AND current knowledge. Answer directly."
        )
        prompt = (f"[{dc['anchor']}]\n\nUser: {question}\n\n" + "\n\n".join(context_parts))
        reply  = ask_ai([{"role":"system","content":system_content},{"role":"user","content":prompt}])
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

# ══════════════════════════════════════════════════════════════
# MEMORY, TASKS, CHAT, RESET  (UNCHANGED)
# ══════════════════════════════════════════════════════════════
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
        tasks.append({"id":len(tasks)+1,"task":task_name,"remind_at":remind_at,
                      "done":False,"created":datetime.now(IST).isoformat()})
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

# ══════════════════════════════════════════════════════════════
# PROFILE ROUTE  (NEW — V8.3)
# ══════════════════════════════════════════════════════════════
@app.route("/profile", methods=["GET", "POST"])
def profile_route():
    """Manage user profile — GET returns current profile, POST saves name from modal."""
    if request.method == "GET":
        profile  = get_user_profile()
        new_user = is_new_user()
        return jsonify({"profile": profile, "is_new_user": new_user})
    # POST — save name from welcome modal
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    if name:
        save_user_profile({"name": name})
    return jsonify({"status": "saved", "name": name})

# ══════════════════════════════════════════════════════════════
# V8.5: WIDGET DETECTION HELPER
# ══════════════════════════════════════════════════════════════
def detect_widget(reply_text):
    """
    Scans AI reply for widget trigger keywords and strips them.
    Groq is instructed via system prompt to include these triggers.

    Trigger format (exact, on its own line):
      SHOW_MAP: <location query>
      SHOW_CHART: <data query>

    Returns tuple:
      (clean_reply, widget_type, widget_query)
      where widget_type is "map", "chart", or None
      and clean_reply has the trigger line completely removed
    """
    text = reply_text.strip()
    clean_reply = text
    widget_type = None
    widget_query = ""

    # Check for SHOW_MAP trigger
    map_match = re.search(r'SHOW_MAP:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    if map_match:
        widget_type = "map"
        widget_query = map_match.group(1).strip()
        # Remove the trigger line from reply - completely strip the entire line
        clean_reply = re.sub(r'\s*SHOW_MAP:\s*(.+?)(?:\n|$)', '', text, flags=re.IGNORECASE).strip()
        return clean_reply, widget_type, widget_query

    # Check for SHOW_CHART trigger
    chart_match = re.search(r'SHOW_CHART:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    if chart_match:
        widget_type = "chart"
        widget_query = chart_match.group(1).strip()
        # Remove the trigger line from reply - completely strip the entire line
        clean_reply = re.sub(r'\s*SHOW_CHART:\s*(.+?)(?:\n|$)', '', text, flags=re.IGNORECASE).strip()
        return clean_reply, widget_type, widget_query

    return text, None, ""

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
        # Extract user info silently (LLM-based, non-blocking)
        extract_and_save_memory(
            user_message,
            groq_key  = GROQ_KEYS[0] if GROQ_KEYS else "",
            save_fn   = save_user_profile   # ← pass profile saver
        )
        # Memory from per-user profile (not shared memory.json)
        memory_ctx       = get_profile_context()
        search_context   = ""
        search_attempted = False

        # ── V8.2: Future Intelligence Layer ──
        future_intent = False
        future_context = ""
        if detects_future_intent(user_message):
            future_intent = True
            today = date.today()
            upcoming = get_upcoming_dates(7)
            future_context = (
                f"\n\n━━━ UPCOMING EVENTS CONTEXT ━━━\n"
                f"Today: {today.strftime('%B %d, %Y')}\n"
                f"Upcoming dates: {', '.join(upcoming)}\n"
                f"The user is asking about upcoming events. Prioritize future-dated "
                f"information and schedules in your response.\n"
            )
            print(f"🔮 Future Intelligence: detected intent for '{user_message[:40]}'")

        if needs_search(user_message):
            search_attempted = True
            search_context = ""
            try:
                search_results = get_web_search(user_message)
                search_context = format_search_results(search_results)
            except Exception as se:
                print(f"Search failed: {se}")
        system_content = build_system_prompt(dc,memory_ctx,bool(search_context),search_attempted)

        # Inject future context if detected
        if future_intent:
            system_content += future_context

        prompt = build_chat_prompt(user_message,search_context,dc,lang_instruction)
        if session_id not in chat_histories:
            chat_histories[session_id] = []
        messages = (
            [{"role":"system","content":system_content}]
            + chat_histories[session_id][-6:]
            + [{"role":"user","content":prompt}]
        )
        reply = ask_ai(messages, temperature=0.4)
        reply_text = "" if reply is None else str(reply)
        reply_text = reply_text.strip()

        chat_histories[session_id].append({"role":"user","content":user_message})
        chat_histories[session_id].append({"role":"assistant","content":reply_text})
        if len(chat_histories[session_id]) > 20:
            chat_histories[session_id] = chat_histories[session_id][-20:]
        
        # Parse sources from search result
        sources = extract_sources(search_context) if search_context else []
        
        # V8.5: Detect widget triggers in reply and strip them from display
        clean_reply, widget_type, widget_query = detect_widget(reply_text)
        
        return jsonify({
            "reply": clean_reply,
            "session_id": session_id,
            "searched": bool(search_context),
            "future_intent": future_intent,
            "sources": sources,
            "widget_type": widget_type,
            "widget_query": widget_query,
        })
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

# ── Force HF Spaces to bind to port 7860 ──
os.environ["PORT"] = "7860"

if __name__ == "__main__":
    dc   = get_date_context()
    print(f"🐼 Panda AI V8.2")
    print(f"   IST: {dc['full_date']} | {dc['time']}")
    print(f"   Groq: {len(GROQ_KEYS)} keys | HF_TOKEN: {'✅' if HF_TOKEN else '❌'}")
    print(f"   Image captioning : {'HF BLIP ✅' if HF_TOKEN else 'disabled — set HF_TOKEN'}")
    print(f"   Audio/Video      : {'Groq Whisper ✅' if GROQ_KEYS else 'disabled — no Groq key'}")
    app.run(debug=False, host="0.0.0.0", port=7860)