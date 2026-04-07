from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
from duckduckgo_search import DDGS
import os
import requests
import json
import re
import random
import time

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
app.config['JSON_AS_ASCII'] = False

# ── Groq Key Rotation ──
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

# ── OpenRouter last-resort fallback ──
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

GROQ_MODEL = "llama-3.3-70b-versatile"

# ── User-Agent Rotation (anti-bot) ──
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

def get_ua():
    return random.choice(USER_AGENTS)

# ── Date helpers ──
def get_today():
    return datetime.now().strftime("%B %d, %Y")

def get_year():
    return str(datetime.now().year)

def get_month_year():
    return datetime.now().strftime("%B %Y")

# ── Clean raw HTML/scraped text ──
def clean_text(text, max_chars=800):
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove JS/CSS blocks
    text = re.sub(r'\{[^}]{0,200}\}', ' ', text)
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove special chars noise
    text = re.sub(r'[|\[\]•©®™]', ' ', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_chars]

# ── Detect if query needs live search ──
def needs_search(query):
    q = query.lower()
    # Skip search for conversational/general queries
    skip_patterns = [
        r'^(hi|hello|hey|thanks|thank you|ok|okay|bye|good\s)',
        r'^(what is your name|who are you|what can you do)',
        r'^(how are you|what\'s up)',
    ]
    for p in skip_patterns:
        if re.match(p, q):
            return False

    # Force search for current/factual queries
    fresh_keywords = [
        "today", "latest", "current", "now", "news", "score", "result",
        "winner", "minister", "cm", "pm", "president", "election", "live",
        "update", "recent", "ipl", "cricket", "price", "weather", "who is",
        "captain", "rank", "chief", "2026", "this year", "this month",
        "yesterday", "tomorrow", "match", "standing", "stock", "rate"
    ]
    return any(kw in q for kw in fresh_keywords)

# ── Fetch full page content ──
def fetch_page(url, timeout=8):
    try:
        headers = {
            "User-Agent": get_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        res = requests.get(url, headers=headers, timeout=timeout)
        if res.status_code == 200:
            return res.text
    except Exception as e:
        print(f"Fetch error {url[:50]}: {e}")
    return ""

# ── Extract readable text from HTML ──
def extract_text(html, max_chars=900):
    if not html:
        return ""
    # Remove script/style blocks entirely
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<nav[^>]*>.*?</nav>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<footer[^>]*>.*?</footer>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<header[^>]*>.*?</header>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    # Extract paragraph and heading text
    paras = re.findall(r'<(?:p|h1|h2|h3|h4|li|td|div)[^>]*>(.*?)</(?:p|h1|h2|h3|h4|li|td|div)>', html, flags=re.DOTALL | re.IGNORECASE)
    text_parts = []
    for p in paras:
        cleaned = clean_text(p, max_chars=300)
        if len(cleaned) > 40:  # skip tiny fragments
            text_parts.append(cleaned)
    full = " ".join(text_parts)
    return full[:max_chars]

# ── Main Search: DuckDuckGo + full page fetch ──
def search_web(query):
    today = get_today()
    year = get_year()
    month_year = get_month_year()

    # Enrich query with date context
    search_query = query.strip()
    if year not in search_query:
        search_query = f"{search_query} {month_year}"

    print(f"🔍 DDG Search: {search_query}")

    results_context = []
    urls_tried = []

    try:
        # Step 1: DuckDuckGo search — get top results
        with DDGS(headers={"User-Agent": get_ua()}) as ddgs:
            ddg_results = list(ddgs.text(
                search_query,
                max_results=6,
                region="in-en",
                safesearch="off",
            ))

        print(f"DDG: {len(ddg_results)} results found")

        # Step 2: For each result — use snippet + fetch full page
        for i, r in enumerate(ddg_results[:5]):
            title = r.get("title", "").strip()
            snippet = clean_text(r.get("body", ""), max_chars=500)
            url = r.get("href", "")

            if not title or not snippet:
                continue

            # Start with snippet
            entry = f"[Source {i+1}: {title}]\n{snippet}"

            # Try to fetch full page for richer content
            if url and url not in urls_tried:
                urls_tried.append(url)
                html = fetch_page(url)
                if html:
                    full_text = extract_text(html, max_chars=900)
                    if full_text and len(full_text) > len(snippet):
                        entry = f"[Source {i+1}: {title} | {url}]\n{full_text}"
                        print(f"  ✅ Full page fetched: {title[:40]}")
                    else:
                        print(f"  ℹ️ Using snippet: {title[:40]}")

                # Small delay between fetches — anti-bot
                time.sleep(random.uniform(0.3, 0.7))

            results_context.append(entry)

        # Step 3: If still poor results, retry with rephrased query
        if len(results_context) < 3:
            rephrased = re.sub(r'\b(current|latest|who is|the)\b', '', query, flags=re.IGNORECASE).strip()
            rephrased = f"{rephrased} {year}".strip()
            print(f"🔍 DDG Retry: {rephrased}")
            with DDGS(headers={"User-Agent": get_ua()}) as ddgs:
                more = list(ddgs.text(rephrased, max_results=4, region="in-en"))
            for i, r in enumerate(more):
                title = r.get("title", "").strip()
                snippet = clean_text(r.get("body", ""), max_chars=500)
                if title and snippet:
                    results_context.append(f"[Source {len(results_context)+1}: {title}]\n{snippet}")

    except Exception as e:
        print(f"DDG search error: {e}")

    # Step 4: Wikipedia fallback
    if len(results_context) < 2:
        try:
            wiki_query = re.sub(r'\s+(current|\d{4}).*$', '', query.strip(), flags=re.IGNORECASE)
            res = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query", "list": "search",
                    "srsearch": wiki_query, "format": "json",
                    "srlimit": 3, "srprop": "snippet|timestamp"
                },
                headers={"User-Agent": "PandaAI/4.2"},
                timeout=8
            )
            if res.status_code == 200:
                data = res.json()
                for item in data.get("query", {}).get("search", []):
                    title = item.get("title", "")
                    snippet = clean_text(item.get("snippet", ""), max_chars=500)
                    ts = item.get("timestamp", "")[:10]
                    if title and snippet:
                        results_context.append(f"[Wikipedia: {title} ({ts})]\n{snippet}")
            print(f"Wikipedia: {len(results_context)} total results")
        except Exception as e:
            print(f"Wikipedia error: {e}")

    print(f"Total context blocks: {len(results_context)}")

    if not results_context:
        return ""

    # Build final context — target 3000-4000 chars
    full_context = f"[LIVE SEARCH — {today}]\n\n" + "\n\n".join(results_context)
    return full_context[:4000]

# ── Groq with Key Rotation ──
def ask_groq(messages):
    if not GROQ_KEYS:
        raise Exception("No Groq API keys configured")

    keys_to_try = list(GROQ_KEYS)
    random.shuffle(keys_to_try)

    for key in keys_to_try:
        key_label = f"...{key[-6:]}"
        try:
            # Small delay before API call — prevents rate limit burst
            time.sleep(random.uniform(0.2, 0.5))

            res = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "max_tokens": 1024,
                    "temperature": 0.3,  # low = factual, less hallucination
                },
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )

            if res.status_code == 429:
                print(f"Groq 429 rate limit: key={key_label} — rotating...")
                time.sleep(1)  # brief wait before next key
                continue
            if res.status_code in (401, 403):
                print(f"Groq {res.status_code}: key={key_label} — skipping")
                continue
            if res.status_code >= 500:
                print(f"Groq server error {res.status_code} — skipping")
                continue

            try:
                data = res.json()
            except Exception:
                print(f"Groq invalid JSON: key={key_label}")
                continue

            if "choices" not in data:
                err = data.get("error", {}).get("message", str(data))
                print(f"Groq error (key={key_label}): {err}")
                continue

            print(f"Groq ✅ model={GROQ_MODEL} key={key_label}")
            return data["choices"][0]["message"]["content"]

        except requests.exceptions.Timeout:
            print(f"Groq timeout: key={key_label}")
            continue
        except Exception as e:
            print(f"Groq exception: {e}")
            continue

    raise Exception("All Groq keys exhausted")

# ── OpenRouter fallback ──
def ask_openrouter(messages):
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY not set")
    res = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json={"model": "openrouter/auto", "messages": messages},
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://panda-ai-iv5u.onrender.com",
            "X-Title": "Panda AI"
        },
        timeout=25
    )
    data = res.json()
    if "choices" not in data:
        raise Exception(data.get("error", {}).get("message", str(data)))
    return data["choices"][0]["message"]["content"]

# ── Master AI call ──
def ask_ai(messages):
    try:
        return ask_groq(messages)
    except Exception as e:
        print(f"Groq failed: {e} — trying OpenRouter...")
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

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "version": "4.2",
        "time": datetime.now().isoformat(),
        "groq_keys": len(GROQ_KEYS),
        "openrouter": bool(OPENROUTER_API_KEY)
    })

@app.route("/news", methods=["GET"])
def get_news():
    try:
        results = []
        with DDGS(headers={"User-Agent": get_ua()}) as ddgs:
            items = list(ddgs.text(
                f"India news today {get_month_year()}",
                max_results=6,
                region="in-en",
                safesearch="off",
            ))
        for r in items:
            title = r.get("title", "").strip()
            if title and len(title) > 15:
                results.append(title)
        return app.response_class(
            response=json.dumps({"news": results[:5], "date": get_today()}, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"News error: {e}")
        return app.response_class(
            response=json.dumps({"news": [], "date": get_today()}, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(force=True)
        user_message = data.get("message", "").strip()
        lang_instruction = data.get("lang_instruction", "").strip()
        session_id = data.get("session_id", "default")

        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        today = get_today()
        now = datetime.now()
        anchor = (
            f"TODAY = {today} | "
            f"DAY = {now.strftime('%A')} | "
            f"YEAR = {now.year} | "
            f"MONTH = {now.strftime('%B')}"
        )

        # ── SEARCH FIRST ──
        search_context = ""
        do_search = needs_search(user_message)

        if do_search:
            try:
                search_context = search_web(user_message)
            except Exception as se:
                print(f"Search failed (non-fatal): {se}")

        # ── Build prompt ──
        if search_context:
            system_content = (
                f"You are Panda AI — a Real-time Data Analyst. {anchor}\n\n"
                "YOUR JOB:\n"
                "1. You will receive a 4000-word LIVE SEARCH CONTEXT below.\n"
                "2. Scan it carefully and extract only the RELEVANT, CURRENT facts.\n"
                "3. IGNORE: ads, menus, footer text, cookie notices, promotional content.\n"
                "4. IGNORE: any data clearly from 2024 or earlier unless no 2025/2026 data exists.\n"
                "5. If the answer IS in the context — state it confidently and cite the source.\n"
                "6. If the answer is NOT clearly in the context — say exactly: "
                "'Information not found in current search results.' then give your best knowledge.\n"
                "7. NEVER hallucinate facts. NEVER say 'I don't have real-time access'.\n"
                "8. Be concise, friendly, and direct.\n"
                "9. Respond in the language requested by the user."
            )
            prompt = (
                f"DATE CONTEXT: {anchor}\n\n"
                f"USER QUESTION: {user_message}\n\n"
                f"=== LIVE SEARCH CONTEXT (4000 words) ===\n"
                f"{search_context}\n"
                f"=== END CONTEXT ===\n\n"
                f"TASK: Extract the direct answer to the user's question from the context above. "
                f"State the answer clearly. If found, cite which source it came from."
            )
        else:
            system_content = (
                f"You are Panda AI — a helpful, friendly AI assistant. {anchor}\n\n"
                "Answer the user's question from your knowledge. "
                "Be concise and friendly. "
                "Respond in the language requested by the user."
            )
            prompt = f"DATE CONTEXT: {anchor}\n\nUser: {user_message}"

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
                "reply": reply,
                "session_id": session_id,
                "searched": bool(search_context)
            }, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )

    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/reset", methods=["POST"])
def reset():
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id", "default")
        if session_id in chat_histories:
            del chat_histories[session_id]
        return jsonify({"status": "reset"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🐼 Panda AI V4.2 running at http://0.0.0.0:{port}")
    print(f"   Groq keys: {len(GROQ_KEYS)} | OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}")
    app.run(debug=False, host="0.0.0.0", port=port)