from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
import os
import requests
import json
import re
import random

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
app.config['JSON_AS_ASCII'] = False

# ── OpenRouter (last resort fallback) ──
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("WARNING: OPENROUTER_API_KEY not found!")

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

# ── Model Strategy: accuracy first, speed fallback ──
GROQ_MODELS = [
    "llama-3.3-70b-versatile",  # primary — high accuracy
    "llama-3.1-8b-instant",     # fallback — fast
]

TODAY = datetime.now().strftime("%B %d, %Y")
CURRENT_YEAR = str(datetime.now().year)
MONTH_YEAR = datetime.now().strftime("%B %Y")

# ── SearXNG Instances ──
SEARXNG_INSTANCES = [
    "https://panda-searxng.onrender.com/search",  # OUR OWN — always first!
    "https://priv.au/search",
    "https://baresearch.org/search",
    "https://search.mdosch.de/search",
    "https://searx.work/search",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }

# ── Increased to 1000 chars for better context ──
def clean_text(text):
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s+', ' ', text).strip()[:1000]

def needs_fresh(query):
    keywords = ["today", "latest", "current", "now", "news", "score",
                "result", "winner", "minister", "cm", "pm", "president",
                "election", "live", "update", "recent", "ipl", "cricket",
                "price", "weather", "who is", "captain", "rank", "chief"]
    return any(kw in query.lower() for kw in keywords)

# ── Rephrase query for retry ──
def rephrase_query(query):
    """Generate alternative search query if first attempt yields poor results."""
    q = query.strip()
    # "current CM of Telangana" → "Telangana Chief Minister 2026"
    q = re.sub(r'\bcurrent\b', '', q, flags=re.IGNORECASE).strip()
    q = re.sub(r'\bwho is\b', '', q, flags=re.IGNORECASE).strip()
    q = re.sub(r'\bthe\b', '', q, flags=re.IGNORECASE).strip()
    if CURRENT_YEAR not in q:
        q = f"{q} {CURRENT_YEAR}"
    return q.strip()

# ── SearXNG Search ──
def search_searxng(query, time_range=None):
    results = []
    instances = [SEARXNG_INSTANCES[0]] + random.sample(SEARXNG_INSTANCES[1:], len(SEARXNG_INSTANCES) - 1)

    for instance in instances:
        if len(results) >= 5:
            break
        try:
            params = {
                "q": query,
                "format": "json",
                "engines": "google,bing,wikipedia",
                "language": "en-IN",
                "region": "in-en",
            }
            if time_range:
                params["time_range"] = time_range

            res = requests.get(instance, params=params, headers=get_headers(), timeout=10)

            if res.status_code == 403:
                print(f"SearXNG 403 forbidden: {instance.split('/')[2]} — skipping")
                continue
            if res.status_code != 200 or not res.text.strip():
                continue

            try:
                data = res.json()
            except:
                continue

            for item in data.get("results", [])[:6]:
                title = item.get("title", "").strip()
                content = clean_text(item.get("content", ""))
                url = item.get("url", "")
                if title and content:
                    results.append(f"• [{title}]({url})\n  {content}")

            if results:
                print(f"SearXNG ✅ {instance.split('/')[2]} — {len(results)} results")
                break

        except requests.exceptions.Timeout:
            print(f"SearXNG timeout: {instance.split('/')[2]}")
        except requests.exceptions.ConnectionError:
            print(f"SearXNG connection error: {instance.split('/')[2]}")
        except Exception as e:
            print(f"SearXNG error: {e}")

    return results

# ── Wikipedia Fallback ──
def search_wikipedia(query):
    results = []
    try:
        clean = re.sub(r'\s+(current|\d{4}).*$', '', query.split("\n")[0].strip(), flags=re.IGNORECASE)
        res = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search",
                "srsearch": clean, "format": "json",
                "srlimit": 4, "srprop": "snippet|timestamp"
            },
            headers={"User-Agent": "PandaAI/1.0 (https://panda-ai-iv5u.onrender.com)"},
            timeout=10
        )
        if res.status_code == 200 and res.text.strip():
            data = res.json()
            for item in data.get("query", {}).get("search", []):
                title = item.get("title", "")
                snippet = clean_text(item.get("snippet", ""))
                timestamp = item.get("timestamp", "")[:10]
                if title and snippet:
                    results.append(f"• [Wikipedia: {title} ({timestamp})]\n  {snippet}")
            print(f"Wikipedia ✅ {len(results)} results")
    except Exception as e:
        print(f"Wikipedia error: {e}")
    return results

# ── Main Search with Re-try on poor results ──
def search_web(query):
    original = query.split("\n")[0].strip()
    is_fresh = needs_fresh(original)

    search_query = original
    if CURRENT_YEAR not in original:
        search_query = f"{original} {MONTH_YEAR if is_fresh else CURRENT_YEAR}"

    print(f"🔍 Search #1: {search_query}")
    results = []

    # Step 1: SearXNG with time filter
    results = search_searxng(search_query, time_range="month" if is_fresh else None)

    # Step 2: SearXNG without time filter
    if len(results) < 3:
        more = search_searxng(search_query)
        for r in more:
            if r not in results:
                results.append(r)

    # Step 3: Re-phrased query retry if still poor results
    if len(results) < 3:
        rephrased = rephrase_query(original)
        if rephrased != search_query:
            print(f"🔍 Search #2 (rephrased): {rephrased}")
            more = search_searxng(rephrased, time_range="month" if is_fresh else None)
            for r in more:
                if r not in results:
                    results.append(r)

    # Step 4: Wikipedia fallback
    if len(results) < 2:
        wiki = search_wikipedia(original)
        results.extend(wiki)

    print(f"Total search results: {len(results)}")

    if results:
        header = f"[Live Search: {TODAY} | SOURCE = REAL-TIME WEB]\n\n"
        return header + "\n\n".join(results[:6])
    return ""

# ── News ──
def get_news_headlines():
    headlines = []
    results = search_searxng(f"India news {MONTH_YEAR}", time_range="day")
    for r in results:
        match = re.match(r'• \[(.+?)\]', r)
        if match:
            title = match.group(1).strip()
            if len(title) > 15 and title not in headlines:
                headlines.append(title)

    if len(headlines) < 3:
        wiki = search_wikipedia(f"India {MONTH_YEAR}")
        for r in wiki:
            match = re.match(r'• \[Wikipedia: (.+?) \(', r)
            if match:
                title = match.group(1).strip()
                if title not in headlines:
                    headlines.append(title)

    return headlines[:5], TODAY

# ── Groq: Key Rotation + Model Fallback ──
def ask_groq(messages):
    if not GROQ_KEYS:
        raise Exception("No Groq API keys configured")

    for model in GROQ_MODELS:
        keys_to_try = list(GROQ_KEYS)
        random.shuffle(keys_to_try)  # spread load

        for key in keys_to_try:
            key_label = f"...{key[-6:]}"
            try:
                res = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": 1024,
                        "temperature": 0.4,  # lower = more factual
                    },
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json"
                    },
                    timeout=25
                )

                # Graceful handling of HTTP errors
                if res.status_code == 429:
                    print(f"Groq 429 rate limit: key={key_label} model={model} — rotating...")
                    continue
                if res.status_code in (401, 403):
                    print(f"Groq {res.status_code} auth error: key={key_label} — skipping")
                    continue
                if res.status_code >= 500:
                    print(f"Groq {res.status_code} server error: model={model} — skipping")
                    continue

                try:
                    data = res.json()
                except Exception:
                    print(f"Groq invalid JSON response: model={model} key={key_label}")
                    continue

                if "choices" not in data:
                    err = data.get("error", {}).get("message", str(data))
                    print(f"Groq error (model={model}, key={key_label}): {err}")
                    continue

                print(f"Groq ✅ model={model} key={key_label}")
                return data["choices"][0]["message"]["content"]

            except requests.exceptions.Timeout:
                print(f"Groq timeout: model={model} key={key_label}")
                continue
            except Exception as e:
                print(f"Groq exception: {e}")
                continue

        print(f"All keys exhausted for model={model} — trying next model...")

    raise Exception("All Groq keys and models exhausted")

# ── OpenRouter Fallback ──
def ask_openrouter(messages):
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY not configured")
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
        if res.status_code in (429, 403):
            raise Exception(f"OpenRouter {res.status_code}")
        data = res.json()
        if "choices" not in data:
            raise Exception(data.get("error", {}).get("message", str(data)))
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise Exception(f"OpenRouter failed: {e}")

# ── Master AI: Groq → OpenRouter ──
def ask_ai(messages):
    try:
        return ask_groq(messages)
    except Exception as e:
        print(f"Groq failed: {e} — falling back to OpenRouter...")
    try:
        reply = ask_openrouter(messages)
        print("OpenRouter ✅ (fallback)")
        return reply
    except Exception as e:
        print(f"OpenRouter also failed: {e}")
        raise Exception("All AI providers failed. Please try again later.")

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
        "time": datetime.now().isoformat(),
        "groq_keys": len(GROQ_KEYS),
        "openrouter": bool(OPENROUTER_API_KEY)
    })

@app.route("/news", methods=["GET"])
def get_news():
    try:
        headlines, today_str = get_news_headlines()
        return app.response_class(
            response=json.dumps({"news": headlines, "date": today_str}, ensure_ascii=False),
            status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"News error: {e}")
        return app.response_class(
            response=json.dumps({"news": [], "date": TODAY}, ensure_ascii=False),
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

        # ── SEARCH FIRST — always ──
        search_results = ""
        try:
            search_results = search_web(user_message)
        except Exception as se:
            print(f"Search failed (non-fatal): {se}")

        today = datetime.now().strftime("%B %d, %Y")

        if search_results:
            prompt = (
                f"Today is {today}.\n\n"
                f"User Question: {user_message}\n\n"
                f"[LIVE SEARCH CONTEXT — REAL-TIME WEB DATA]\n"
                f"{search_results}\n\n"
                f"Task: Carefully read the search results above and directly answer the user's question. "
                f"Extract the specific fact being asked (e.g. a person's name, a score, a date). "
                f"If the exact answer is in the context, state it confidently. "
                f"If the context gives strong clues but not the exact answer, combine it with your "
                f"high-confidence knowledge to complete the answer — but say so. "
                f"Cite the source title when helpful."
            )
            system_content = (
                f"You are Panda AI — a highly accurate, real-time AI assistant. Today is {today}.\n\n"
                "RULES:\n"
                "1. [LIVE SEARCH CONTEXT] = highest priority. Always use it over your training data.\n"
                "2. Extract direct answers from the context — names, scores, dates, positions.\n"
                "3. If context partially answers the question, combine it with high-confidence "
                "   internal knowledge carefully, and flag what came from where.\n"
                "4. NEVER say 'I don't have real-time info' when search context is provided.\n"
                "5. NEVER mention training cutoff or knowledge limitations.\n"
                "6. If context truly has no relevant info, say: 'The search didn't return clear "
                "   results for this — here is what I know:' and answer from knowledge.\n"
                "7. Be friendly, direct, and concise.\n"
                "8. Respond fully in the language requested by the user."
            )
        else:
            prompt = f"Today is {today}.\n\nUser Question: {user_message}"
            system_content = (
                f"You are Panda AI. Today is {today}.\n"
                "Live search is temporarily unavailable. "
                "Answer from your training knowledge, always prefixing with: "
                "'Based on my knowledge (please verify for the latest):'\n"
                "Never present outdated data as current fact. Be friendly and helpful. "
                "Respond in the language requested by the user."
            )

        if lang_instruction:
            prompt = f"{prompt}\n\n[LANGUAGE INSTRUCTION: {lang_instruction}]"

        if session_id not in chat_histories:
            chat_histories[session_id] = []

        chat_histories[session_id].append({"role": "user", "content": prompt})
        messages = [{"role": "system", "content": system_content}] + chat_histories[session_id][-8:]

        reply = ask_ai(messages)
        chat_histories[session_id].append({"role": "assistant", "content": reply})

        return app.response_class(
            response=json.dumps({
                "reply": reply,
                "session_id": session_id,
                "searched": bool(search_results)
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
    print(f"🐼 Panda AI V4 running at http://0.0.0.0:{port}")
    print(f"   Groq keys: {len(GROQ_KEYS)} | OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}")
    app.run(debug=False, host="0.0.0.0", port=port)