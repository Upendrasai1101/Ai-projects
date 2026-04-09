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
GROQ_MODEL         = "llama-3.3-70b-versatile"

# ── Bamboo Engine — rstrip('/') fixes trailing slash typo ──
BAMBOO_URL        = os.getenv("BAMBOO_URL", "https://bamboo-engine.onrender.com").rstrip("/")
SEARXNG_SECRET_KEY = os.getenv("SEARXNG_SECRET_KEY", "")

print(f"🎋 Bamboo Engine: {BAMBOO_URL}")

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
        "date":       n.strftime("%B %d, %Y"),
        "day":        n.strftime("%A"),
        "year":       str(n.year),
        "month":      n.strftime("%B"),
        "month_year": n.strftime("%B %Y"),
        "anchor":     f"TODAY={n.strftime('%B %d, %Y')} | DAY={n.strftime('%A')} | YEAR={n.year} | MONTH={n.strftime('%B')}"
    }

# ── Clean text ──
def clean_scraped(text, max_chars=900):
    if not text:
        return ""
    text = re.sub(r'<(script|style|nav|footer|header|aside|form)[^>]*>.*?</\1>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    noise_patterns = [
        r'accept\s+cookies?', r'privacy\s+policy', r'terms\s+of\s+service',
        r'subscribe\s+now', r'sign\s+up', r'log\s+in', r'advertisement',
        r'sponsored', r'click\s+here', r'read\s+more', r'follow\s+us',
        r'share\s+this', r'copyright\s+\d{4}', r'all\s+rights\s+reserved',
    ]
    for p in noise_patterns:
        text = re.sub(p, ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'[|•©®™<>{}[\]\\]', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text[:max_chars]

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

# ── Bamboo Engine Search — fixed with debug logging + retry + robust key extraction ──
def bamboo_search(query, time_range=None):
    results = []

    params = {
        "q":        query,
        "format":   "json",
        "engines":  "google,bing,wikipedia",
        "language": "en-IN",
        "region":   "in-en",
    }
    if time_range:
        params["time_range"] = time_range

    headers = {
        "User-Agent":      get_ua(),
        "Accept":          "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if SEARXNG_SECRET_KEY:
        headers["X-Searxng-Key"] = SEARXNG_SECRET_KEY

    search_url = f"{BAMBOO_URL}/search"
    print(f"🎋 Bamboo URL: {search_url}")
    print(f"🎋 Query: {query[:80]}")
    print(f"🎋 Secret key set: {bool(SEARXNG_SECRET_KEY)}")

    # ── Retry loop: try twice before giving up ──
    for attempt in range(1, 3):
        try:
            print(f"🎋 Attempt {attempt}...")
            res = requests.get(
                search_url,
                params=params,
                headers=headers,
                timeout=20  # 20s for Render cold start
            )

            print(f"🎋 HTTP status: {res.status_code}")
            print(f"🎋 Response length: {len(res.text)} chars")

            # Debug: print first 300 chars of raw response
            print(f"🎋 Raw response preview: {res.text[:300]}")

            if res.status_code == 403:
                print("🎋 403 — check SEARXNG_SECRET_KEY or SearXNG limiter config")
                return []
            if res.status_code == 429:
                print("🎋 429 — rate limited")
                time.sleep(2)
                continue
            if res.status_code != 200:
                print(f"🎋 Unexpected status: {res.status_code}")
                if attempt < 2:
                    time.sleep(1)
                continue

            if not res.text.strip():
                print("🎋 Empty response body")
                if attempt < 2:
                    time.sleep(1)
                continue

            # Parse JSON
            try:
                data = res.json()
            except Exception as je:
                print(f"🎋 JSON parse error: {je}")
                print(f"🎋 Raw text: {res.text[:500]}")
                if attempt < 2:
                    time.sleep(1)
                continue

            # Debug: print top-level keys
            print(f"🎋 JSON keys: {list(data.keys())}")

            raw_results = data.get("results", [])
            print(f"🎋 Raw results count: {len(raw_results)}")

            if not raw_results:
                print("🎋 No results in JSON — retrying...")
                if attempt < 2:
                    time.sleep(1)
                continue

            # ── Robust field extraction ──
            # SearXNG uses 'content' for snippet, but also check 'snippet', 'description'
            for i, item in enumerate(raw_results[:6]):
                title = (item.get("title") or "").strip()
                url   = (item.get("url") or item.get("href") or "")

                # Try multiple snippet keys
                snippet_raw = (
                    item.get("content") or
                    item.get("snippet") or
                    item.get("description") or
                    item.get("text") or
                    ""
                )
                snippet = clean_scraped(snippet_raw, max_chars=700)

                # Debug each result
                print(f"  Result {i+1}: title='{title[:40]}' snippet_len={len(snippet)} url='{url[:50]}'")

                # Accept result even if snippet is short — title alone is useful
                if not title:
                    continue

                # If snippet empty, use title as minimal context
                if not snippet:
                    snippet = f"Source: {title}"

                results.append({
                    "title":   title,
                    "snippet": snippet,
                    "url":     url,
                })

            print(f"🎋 Parsed {len(results)} usable results")

            if results:
                break  # success — stop retrying

            # No usable results after parsing, retry
            if attempt < 2:
                print("🎋 0 usable results after parsing — retrying in 1s...")
                time.sleep(1)

        except requests.exceptions.Timeout:
            print(f"🎋 Timeout on attempt {attempt}")
            if attempt < 2:
                time.sleep(1)
        except requests.exceptions.ConnectionError as ce:
            print(f"🎋 Connection error: {ce}")
            if attempt < 2:
                time.sleep(1)
        except Exception as e:
            print(f"🎋 Unexpected error: {e}")
            if attempt < 2:
                time.sleep(1)

    return results

# ── Wikipedia fallback (always-on) ──
def search_wikipedia(query):
    results = []
    try:
        clean_q = re.sub(r'\b(current|latest|today|who is|the|2026|2025|April|March)\b', '', query, flags=re.IGNORECASE).strip()
        res = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search",
                "srsearch": clean_q, "format": "json",
                "srlimit": 3, "srprop": "snippet|timestamp"
            },
            headers={"User-Agent": "PandaAI/4.3 (panda-ai-iv5u.onrender.com)"},
            timeout=8
        )
        if res.status_code == 200:
            items = res.json().get("query", {}).get("search", [])
            for item in items:
                title   = item.get("title", "")
                snippet = clean_scraped(item.get("snippet", ""), 600)
                ts      = item.get("timestamp", "")[:10]
                if title and snippet:
                    results.append({
                        "title":   f"Wikipedia: {title} (updated {ts})",
                        "snippet": snippet,
                        "url":     f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                    })
        print(f"Wikipedia: {len(results)} results")
    except Exception as e:
        print(f"Wikipedia error: {e}")
    return results

# ── Main search_web ──
def search_web(query):
    dt       = now_str()
    original = query.strip()

    is_fresh = any(kw in original.lower() for kw in [
        "today","latest","current","now","live","score","news","yesterday","tomorrow"
    ])

    query_variations = [
        f"{original} {dt['month_year']}",
        f"latest {original} {dt['year']}",
        f"{re.sub(r'who is |what is |the ', '', original, flags=re.IGNORECASE).strip()} {dt['year']}",
    ]

    all_results = []

    for attempt, q in enumerate(query_variations, 1):
        if len(all_results) >= 4:
            break
        print(f"🔍 Search variation {attempt}: {q}")
        bamboo_results = bamboo_search(q, time_range="month" if is_fresh else None)

        for r in bamboo_results:
            if r["url"] and any(r["url"] == x.get("url") for x in all_results):
                continue
            all_results.append(r)

        if len(all_results) >= 3:
            print(f"✅ Got {len(all_results)} results on variation {attempt}")
            break

        if attempt < len(query_variations):
            time.sleep(0.5)

    # Wikipedia fallback
    if len(all_results) < 2:
        print("⚠️ Bamboo failed — Wikipedia fallback")
        wiki = search_wikipedia(original)
        all_results.extend(wiki)

    print(f"📦 Total results: {len(all_results)}")

    if not all_results:
        return ""

    # ── Build context string ──
    context_blocks = []
    for i, r in enumerate(all_results[:5], 1):
        block = (
            f"[Result {i}: {r['title']}]\n"
            f"URL: {r['url']}\n"
            f"Content: {r['snippet']}"
        )
        context_blocks.append(block)

    context = f"[LIVE DATA — {dt['date']} | Source: Bamboo Engine]\n\n" + "\n\n".join(context_blocks)

    # ── Safety net: never pass empty context if results found ──
    if not context.strip():
        context = f"[Search completed on {dt['date']}] No specific snippets extracted, but {len(all_results)} sources were found."

    print(f"📝 Context length: {len(context)} chars")
    return context[:4500]

# ── Groq with Key Rotation ──
def ask_groq(messages):
    if not GROQ_KEYS:
        raise Exception("No Groq API keys configured")

    keys_to_try = list(GROQ_KEYS)
    random.shuffle(keys_to_try)

    for key in keys_to_try:
        key_label = f"...{key[-6:]}"
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
                    "Content-Type":  "application/json"
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
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://panda-ai-iv5u.onrender.com",
                "X-Title":       "Panda AI"
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
        "status":     "ok",
        "version":    "4.3-fix",
        "time":       datetime.now().isoformat(),
        "groq_keys":  len(GROQ_KEYS),
        "bamboo":     BAMBOO_URL,
        "secret_key": bool(SEARXNG_SECRET_KEY),
        "openrouter": bool(OPENROUTER_API_KEY),
    })

@app.route("/news", methods=["GET"])
def get_news():
    dt = now_str()
    try:
        results = bamboo_search(f"India top news today {dt['month_year']}", time_range="day")
        if not results:
            results = search_wikipedia(f"India current events {dt['month_year']}")
        headlines = []
        for r in results:
            title = re.sub(r'^Wikipedia:\s*', '', r.get("title", "").strip())
            if len(title) > 15:
                headlines.append(title)
        return app.response_class(
            response=json.dumps({"news": headlines[:5], "date": dt["date"]}, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"News error: {e}")
        return app.response_class(
            response=json.dumps({"news": [], "date": dt["date"]}, ensure_ascii=False),
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

        dt = now_str()

        # ── SEARCH FIRST ──
        search_context = ""
        if needs_search(user_message):
            try:
                search_context = search_web(user_message)
            except Exception as se:
                print(f"Search failed (non-fatal): {se}")

        # ── Build prompts ──
        if search_context:
            system_content = (
                f"You are Panda AI — a Real-time Data Analyst. {dt['anchor']}\n\n"
                "STRICT RULES:\n"
                "1. You receive LIVE SEARCH CONTEXT from Bamboo Engine (real-time web data).\n"
                "2. READ it carefully. Extract ONLY relevant, current facts.\n"
                "3. DO NOT use internal training data for current officials, events, scores, or news.\n"
                "4. IGNORE: ads, cookie notices, navigation menus, footer text, promotional content.\n"
                "5. IGNORE: any data clearly from 2024 or earlier UNLESS no newer data exists.\n"
                "6. Answer found in context → state confidently, cite the source title.\n"
                "7. Answer NOT found in context → say: 'Current data not available from search results.' "
                "Then share training knowledge with a clear disclaimer.\n"
                "8. NEVER hallucinate names, positions, scores, or facts.\n"
                "9. Be concise, friendly, and direct.\n"
                "10. Respond in the language requested by the user."
            )
            prompt = (
                f"DATE: {dt['anchor']}\n\n"
                f"USER QUESTION: {user_message}\n\n"
                f"=== LIVE SEARCH CONTEXT (Bamboo Engine) ===\n"
                f"{search_context}\n"
                f"=== END CONTEXT ===\n\n"
                f"Find the direct answer from the context above. "
                f"Cite the source title. If not found, say 'Current data not available.'"
            )
        else:
            system_content = (
                f"You are Panda AI — a helpful AI assistant. {dt['anchor']}\n"
                "Answer clearly and concisely from your knowledge. "
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
                "reply":      reply,
                "session_id": session_id,
                "searched":   bool(search_context)
            }, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )

    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/reset", methods=["POST"])
def reset():
    try:
        body       = request.get_json(force=True)
        session_id = body.get("session_id", "default")
        if session_id in chat_histories:
            del chat_histories[session_id]
        return jsonify({"status": "reset"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🐼 Panda AI V4.3-fix — http://0.0.0.0:{port}")
    print(f"   Groq: {len(GROQ_KEYS)} keys | Bamboo: {BAMBOO_URL} | Secret: {'✅' if SEARXNG_SECRET_KEY else '❌'} | OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}")
    app.run(debug=False, host="0.0.0.0", port=port)