from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
import os
import requests
from bs4 import BeautifulSoup
import urllib.parse
import json

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ── Multi-source Search ──
def search_web(query, max_results=6):
    """Try multiple search sources for best accuracy"""
    clean_query = query.split("\n")[0].strip()
    current_year = datetime.now().year
    today_str = datetime.now().strftime("%B %d, %Y")

    if str(current_year) not in clean_query:
        clean_query = f"{clean_query} {current_year}"

    results = []

    # Source 1: DuckDuckGo with different user agents
    user_agents = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    ]

    for ua in user_agents:
        if len(results) >= 4:
            break
        try:
            headers = {
                "User-Agent": ua,
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml",
                "Cache-Control": "no-cache",
            }
            for df in ["m", None]:
                params = {"q": clean_query, "kl": "in-en"}
                if df:
                    params["df"] = df
                url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(params)
                res = requests.get(url, headers=headers, timeout=10)
                res.encoding = "utf-8"
                soup = BeautifulSoup(res.text, "html.parser")
                for r in soup.select(".result__body")[:max_results]:
                    title = r.select_one(".result__title")
                    snippet = r.select_one(".result__snippet")
                    if snippet:
                        t = title.get_text(strip=True) if title else ""
                        s = snippet.get_text(strip=True)
                        entry = f"• [{t}] {s}"
                        if s and entry not in results:
                            results.append(entry)
                if len(results) >= 4:
                    break
        except:
            continue

    # Source 2: Wikipedia API (always fresh, never blocked)
    try:
        wiki_query = query.split("\n")[0].strip()
        wiki_url = "https://en.wikipedia.org/w/api.php"
        wiki_params = {
            "action": "query",
            "list": "search",
            "srsearch": wiki_query,
            "format": "json",
            "srlimit": 3,
            "srprop": "snippet|timestamp"
        }
        wiki_res = requests.get(wiki_url, params=wiki_params, timeout=8)
        wiki_data = wiki_res.json()
        for item in wiki_data.get("query", {}).get("search", []):
            title = item.get("title", "")
            snippet = BeautifulSoup(item.get("snippet", ""), "html.parser").get_text()
            timestamp = item.get("timestamp", "")[:10]
            if snippet:
                entry = f"• [Wikipedia - {title} ({timestamp})] {snippet}"
                if entry not in results:
                    results.append(entry)
    except:
        pass

    # Source 3: DuckDuckGo Instant Answer API
    try:
        ddg_api = "https://api.duckduckgo.com/"
        params = {"q": clean_query, "format": "json", "no_html": "1"}
        res = requests.get(ddg_api, params=params, timeout=8)
        data = res.json()
        if data.get("AbstractText"):
            entry = f"• [DuckDuckGo Summary] {data['AbstractText']}"
            if entry not in results:
                results.insert(0, entry)
        for rt in data.get("RelatedTopics", [])[:3]:
            if isinstance(rt, dict) and rt.get("Text"):
                entry = f"• [Related] {rt['Text']}"
                if entry not in results:
                    results.append(entry)
    except:
        pass

    if results:
        header = f"[Search date: {today_str}. CRITICAL: Use ONLY these results for current facts. Do NOT use internal training data for current events.]\n"
        return header + "\n\n".join(results[:max_results])
    return ""


def get_news_headlines():
    """Get news from multiple sources"""
    today_str = datetime.now().strftime("%B %d, %Y")
    year = datetime.now().year
    headlines = []

    # Source 1: DuckDuckGo news
    for ua in [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    ]:
        if len(headlines) >= 5:
            break
        try:
            headers = {"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"}
            for df in ["d", "w"]:
                params = {"q": f"India news today {year}", "kl": "in-en", "df": df}
                url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(params)
                res = requests.get(url, headers=headers, timeout=8)
                res.encoding = "utf-8"
                soup = BeautifulSoup(res.text, "html.parser")
                for r in soup.select(".result__body")[:8]:
                    title = r.select_one(".result__title")
                    if title:
                        t = title.get_text(strip=True)
                        if t and t not in headlines and len(t) > 15:
                            headlines.append(t)
                if len(headlines) >= 5:
                    break
        except:
            continue

    # Source 2: Wikipedia current events
    if len(headlines) < 3:
        try:
            wiki_url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": f"India news {datetime.now().strftime('%B %Y')}",
                "format": "json",
                "srlimit": 5
            }
            res = requests.get(wiki_url, params=params, timeout=8)
            data = res.json()
            for item in data.get("query", {}).get("search", []):
                t = item.get("title", "")
                if t and t not in headlines:
                    headlines.append(t)
        except:
            pass

    return headlines[:5], today_str


# ── OpenRouter Chat ──
def ask_openrouter(messages):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://panda-ai-iv5u.onrender.com",
        "X-Title": "Panda AI"
    }
    payload = {"model": "openrouter/auto", "messages": messages}
    res = requests.post(url, json=payload, headers=headers, timeout=30)
    res.encoding = "utf-8"
    data = res.json()
    if "choices" not in data:
        raise Exception(data.get("error", {}).get("message", str(data)))
    return data["choices"][0]["message"]["content"]


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


@app.route("/news", methods=["GET"])
def get_news():
    try:
        headlines, today_str = get_news_headlines()
        response = app.response_class(
            response=json.dumps({"news": headlines, "date": today_str}, ensure_ascii=False),
            status=200,
            mimetype="application/json; charset=utf-8"
        )
        return response
    except Exception as e:
        return jsonify({"news": [], "error": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    user_message = data.get("message", "").strip()
    lang_instruction = data.get("lang_instruction", "").strip()
    session_id = data.get("session_id", "default")

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    try:
        search_results = search_web(user_message)
        today = datetime.now().strftime("%B %d, %Y")

        if search_results:
            prompt = f"{user_message}\n\n[SEARCH RESULTS]\n{search_results}"
        else:
            prompt = user_message

        if lang_instruction:
            prompt = f"{prompt}\n\n[{lang_instruction}]"

        system_msg = {
            "role": "system",
            "content": (
                f"You are Panda AI, a smart, calm and helpful AI assistant. "
                f"Today is {today}.\n\n"
                "CRITICAL RULES — STRICTLY FOLLOW:\n"
                "1. [SEARCH RESULTS] = ABSOLUTE TRUTH. Always use them over your training data.\n"
                "2. For current roles (minister, CM, PM, captain, CEO, winner etc.) — use ONLY search results.\n"
                "3. Search results include Wikipedia and DuckDuckGo — they are current and accurate.\n"
                "4. NEVER say 'I don't have current information' when [SEARCH RESULTS] are provided.\n"
                "5. If search results are provided — use them and answer confidently.\n"
                "6. Only say 'please verify online' if NO search results were provided.\n"
                "7. Be clear, friendly and concise.\n"
                "8. Respond fully in the language requested."
            )
        }

        if session_id not in chat_histories:
            chat_histories[session_id] = []

        chat_histories[session_id].append({"role": "user", "content": prompt})
        messages = [system_msg] + chat_histories[session_id][-10:]
        reply = ask_openrouter(messages)
        chat_histories[session_id].append({"role": "assistant", "content": reply})

        response = app.response_class(
            response=json.dumps({
                "reply": reply,
                "session_id": session_id,
                "searched": bool(search_results)
            }, ensure_ascii=False),
            status=200,
            mimetype="application/json; charset=utf-8"
        )
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/reset", methods=["POST"])
def reset():
    data = request.get_json(force=True)
    session_id = data.get("session_id", "default")
    if session_id in chat_histories:
        del chat_histories[session_id]
    return jsonify({"status": "reset", "session_id": session_id})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🐼 Panda AI is running at http://0.0.0.0:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)