from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
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

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# ── User-Agent Pool ──
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

def get_ua():
    return random.choice(USER_AGENTS)

def now_str():
    n = datetime.now()
    return {
        "date": n.strftime("%B %d, %Y"),
        "day": n.strftime("%A"),
        "year": str(n.year),
        "month": n.strftime("%B"),
        "month_year": n.strftime("%B %Y"),
        "anchor": f"TODAY={n.strftime('%B %d, %Y')} | DAY={n.strftime('%A')} | YEAR={n.year} | MONTH={n.strftime('%B')}"
    }

# ── Clean scraped text — remove ads/nav/cookie noise ──
def clean_scraped(text, max_chars=900):
    if not text:
        return ""
    # Remove script/style/nav/footer content
    text = re.sub(r'<(script|style|nav|footer|header|aside|form)[^>]*>.*?</\1>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove all HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove cookie/ad phrases
    noise_patterns = [
        r'accept\s+cookies?', r'privacy\s+policy', r'terms\s+of\s+service',
        r'subscribe\s+now', r'sign\s+up', r'log\s+in', r'advertisement',
        r'sponsored', r'click\s+here', r'read\s+more', r'follow\s+us',
        r'share\s+this', r'copyright\s+\d{4}', r'all\s+rights\s+reserved',
    ]
    for p in noise_patterns:
        text = re.sub(p, ' ', text, flags=re.IGNORECASE)
    # Remove special chars noise
    text = re.sub(r'[|•©®™<>{}[\]\\]', ' ', text)
    # Collapse whitespace
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text[:max_chars]

# ── Fetch and extract readable text from a URL ──
def fetch_page_text(url, max_chars=900):
    try:
        headers = {
            "User-Agent": get_ua(),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }
        res = requests.get(url, headers=headers, timeout=7, allow_redirects=True)
        if res.status_code != 200:
            return ""
        html = res.text
        # Extract paragraph/heading content only
        chunks = re.findall(
            r'<(?:p|h1|h2|h3|h4|li|td)[^>]*>(.*?)</(?:p|h1|h2|h3|h4|li|td)>',
            html, flags=re.DOTALL | re.IGNORECASE
        )
        parts = []
        for c in chunks:
            cleaned = clean_scraped(c, max_chars=250)
            if len(cleaned) > 50:
                parts.append(cleaned)
        return clean_scraped(" ".join(parts), max_chars=max_chars)
    except Exception as e:
        print(f"  Fetch error {url[:50]}: {e}")
        return ""

# ── DuckDuckGo search via HTML scraping (no library needed) ──
def ddg_search(query, max_results=6):
    """Search DuckDuckGo HTML and parse results."""
    results = []
    try:
        headers = {
            "User-Agent": get_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        params = {
            "q": query,
            "kl": "in-en",   # India region
            "kp": "-1",      # safe search off
            "kaf": "1",
        }
        res = requests.get(
            "https://html.duckduckgo.com/html/",
            params=params,
            headers=headers,
            timeout=10
        )

        if res.status_code != 200:
            print(f"DDG status: {res.status_code}")
            return []

        html = res.text

        # Extract result blocks
        blocks = re.findall(
            r'<div class="result[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
            html, flags=re.DOTALL
        )

        for block in blocks[:max_results]:
            # Title
            title_m = re.search(r'class="result__a"[^>]*>(.*?)</a>', block, re.DOTALL)
            title = clean_scraped(title_m.group(1), 200) if title_m else ""

            # URL
            url_m = re.search(r'href="([^"]+)"', block)
            url = url_m.group(1) if url_m else ""
            if url.startswith("//duckduckgo.com") or not url.startswith("http"):
                url = ""

            # Snippet
            snip_m = re.search(r'class="result__snippet"[^>]*>(.*?)</(?:a|span)>', block, re.DOTALL)
            snippet = clean_scraped(snip_m.group(1), 500) if snip_m else ""

            if title and snippet:
                results.append({"title": title, "url": url, "snippet": snippet})

        print(f"DDG parsed: {len(results)} results for '{query[:50]}'")

    except Exception as e:
        print(f"DDG error: {e}")

    return results

# ── Detect if query needs live search ──
def needs_search(query):
    q = query.lower().strip()
    skip = re.match(
        r'^(hi|hello|hey|thanks|thank you|ok|okay|bye|good\s+morning|good\s+night|'
        r'what is your name|who are you|what can you do|how are you)',
        q
    )
    if skip:
        return False
    live_keywords = [
        "today", "latest", "current", "now", "news", "score", "result",
        "winner", "minister", "cm", "pm", "president", "election", "live",
        "update", "recent", "ipl", "cricket", "price", "weather", "who is",
        "captain", "rank", "chief", "2026", "this year", "this month",
        "yesterday", "tomorrow", "match", "standing", "stock", "rate",
        "vs", "versus", "game", "play", "win", "lose"
    ]
    return any(kw in q for kw in live_keywords)

# ── Smart Search with 3-variation fallback loop ──
def search_web(query):
    dt = now_str()
    original = query.strip()

    # Build 3 query variations to try
    query_variations = [
        f"{original} {dt['month_year']}",                          # Variation 1: original + month year
        f"latest {original} {dt['year']}",                         # Variation 2: latest + year
        f"current {re.sub(r'who is |what is |the ', '', original, flags=re.IGNORECASE).strip()} {dt['year']}",  # Variation 3: stripped + year
    ]

    all_results = []
    used_urls = set()

    # ── Loop through variations until we get good results ──
    for attempt, q in enumerate(query_variations, 1):
        if len(all_results) >= 4:
            break

        print(f"🔍 Search attempt {attempt}: {q}")
        ddg_results = ddg_search(q, max_results=6)

        if not ddg_results:
            print(f"  ❌ 0 results on attempt {attempt}, trying next variation...")
            time.sleep(random.uniform(0.5, 1.0))
            continue

        for r in ddg_results:
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            url = r.get("url", "")

            if not title or not snippet:
                continue

            # Start with snippet
            content = snippet

            # Try fetching full page for richer content
            if url and url not in used_urls and len(all_results) < 5:
                used_urls.add(url)
                full = fetch_page_text(url, max_chars=900)
                if full and len(full) > len(snippet):
                    content = full
                    print(f"  ✅ Full page: {title[:40]}")
                time.sleep(random.uniform(0.2, 0.5))  # anti-bot delay

            all_results.append(f"[Source {len(all_results)+1}: {title}]\n{content}")

        if len(all_results) >= 3:
            print(f"  ✅ Got {len(all_results)} results on attempt {attempt}")
            break

        time.sleep(random.uniform(0.5, 1.0))

    # ── Wikipedia fallback if still poor ──
    if len(all_results) < 2:
        print("⚠️ DDG failed — trying Wikipedia...")
        try:
            wiki_q = re.sub(r'\s+(current|latest|\d{4}).*$', '', original, flags=re.IGNORECASE).strip()
            res = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query", "list": "search",
                    "srsearch": wiki_q, "format": "json",
                    "srlimit": 3, "srprop": "snippet|timestamp"
                },
                headers={"User-Agent": "PandaAI/4.2 (https://panda-ai-iv5u.onrender.com)"},
                timeout=8
            )
            if res.status_code == 200:
                data = res.json()
                for item in data.get("query", {}).get("search", []):
                    title = item.get("title", "")
                    snippet = clean_scraped(item.get("snippet", ""), 500)
                    ts = item.get("timestamp", "")[:10]
                    if title and snippet:
                        all_results.append(f"[Wikipedia: {title} ({ts})]\n{snippet}")
            print(f"Wikipedia: {len(all_results)} total")
        except Exception as e:
            print(f"Wikipedia error: {e}")

    print(f"📦 Total context blocks: {len(all_results)}")

    if not all_results:
        return ""

    # ── Build ~4000 char context ──
    context = f"[LIVE SEARCH RESULTS — {dt['date']}]\n\n" + "\n\n".join(all_results)
    return context[:4000]

# ── Groq with Key Rotation ──
def ask_groq(messages):
    if not GROQ_KEYS:
        raise Exception("No Groq API keys configured")

    keys_to_try = list(GROQ_KEYS)
    random.shuffle(keys_to_try)

    for key in keys_to_try:
        key_label = f"...{key[-6:]}"
        try:
            time.sleep(random.uniform(0.2, 0.4))  # anti rate-limit

            res = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "max_tokens": 1024,
                    "temperature": 0.2,
                },
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )

            if res.status_code == 429:
                print(f"Groq 429: key={key_label} — rotating...")
                time.sleep(1.5)
                continue
            if res.status_code in (401, 403):
                print(f"Groq {res.status_code}: key={key_label} — skipping")
                continue
            if res.status_code >= 500:
                print(f"Groq server error {res.status_code}")
                continue

            try:
                data = res.json()
            except Exception:
                print(f"Groq invalid JSON: key={key_label}")
                continue

            if "choices" not in data:
                err = data.get("error", {}).get("message", str(data))
                print(f"Groq no choices (key={key_label}): {err}")
                continue

            print(f"Groq ✅ key={key_label}")
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
    try:
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
    except Exception as e:
        raise Exception(f"OpenRouter failed: {e}")

# ── Master AI ──
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
        "version": "4.2-final",
        "time": datetime.now().isoformat(),
        "groq_keys": len(GROQ_KEYS),
        "openrouter": bool(OPENROUTER_API_KEY)
    })

@app.route("/news", methods=["GET"])
def get_news():
    dt = now_str()
    try:
        results = ddg_search(f"India top news today {dt['month_year']}", max_results=6)
        headlines = []
        for r in results:
            title = r.get("title", "").strip()
            if title and len(title) > 15:
                headlines.append(title)
        return app.response_class(
            response=json.dumps({"news": headlines[:5], "date": dt['date']}, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"News error: {e}")
        return app.response_class(
            response=json.dumps({"news": [], "date": dt['date']}, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )

@app.route("/chat", methods=["POST"])
def chat():
    try:
        body = request.get_json(force=True)
        user_message = body.get("message", "").strip()
        lang_instruction = body.get("lang_instruction", "").strip()
        session_id = body.get("session_id", "default")

        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        dt = now_str()

        # ── SEARCH FIRST ──
        search_context = ""
        do_search = needs_search(user_message)
        if do_search:
            try:
                search_context = search_web(user_message)
            except Exception as se:
                print(f"Search failed (non-fatal): {se}")

        # ── Build prompts ──
        if search_context:
            system_content = (
                f"You are Panda AI — a Real-time Data Analyst. {dt['anchor']}\n\n"
                "STRICT RULES:\n"
                "1. You will receive a LIVE SEARCH CONTEXT below (~4000 characters of real web data).\n"
                "2. READ the context carefully. Extract ONLY relevant, current facts.\n"
                "3. DO NOT use your internal training data for current officials, events, scores, or news.\n"
                "4. IGNORE: ads, cookie notices, navigation menus, footer text, promotional content.\n"
                "5. IGNORE: any data clearly from 2024 or earlier UNLESS no newer data exists.\n"
                "6. If the answer IS found in context → state it confidently, cite the source title.\n"
                "7. If the answer is NOT found in context → say exactly: 'Current data not available "
                "from search results.' Then optionally share what you know from training with a clear disclaimer.\n"
                "8. NEVER hallucinate names, positions, scores, or facts.\n"
                "9. Be concise, friendly, and direct.\n"
                "10. Respond in the language requested by the user."
            )
            prompt = (
                f"DATE: {dt['anchor']}\n\n"
                f"USER QUESTION: {user_message}\n\n"
                f"=== LIVE SEARCH CONTEXT ===\n"
                f"{search_context}\n"
                f"=== END CONTEXT ===\n\n"
                f"INSTRUCTION: Find the direct answer to the user's question from the context above. "
                f"If found, answer confidently and cite the source. "
                f"If not found, say 'Current data not available from search results.'"
            )
        else:
            system_content = (
                f"You are Panda AI — a helpful AI assistant. {dt['anchor']}\n"
                "Answer the user's question clearly and concisely from your knowledge. "
                "Respond in the language requested by the user."
            )
            prompt = f"DATE: {dt['anchor']}\n\nUser: {user_message}"

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
        body = request.get_json(force=True)
        session_id = body.get("session_id", "default")
        if session_id in chat_histories:
            del chat_histories[session_id]
        return jsonify({"status": "reset"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🐼 Panda AI V4.2 Final — http://0.0.0.0:{port}")
    print(f"   Groq keys: {len(GROQ_KEYS)} | OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}")
    app.run(debug=False, host="0.0.0.0", port=port)