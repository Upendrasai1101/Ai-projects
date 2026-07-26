# --- FILE: media_generator.py --- V8 Studio
"""
media_generator.py — Panda AI V8 Studio
Standalone media module. All three engines live here.
app.py imports and calls these functions from /generate-media.

Engines:
  IMAGE  → Cloudflare Workers AI SD XL (2-account key rotation)
           Fallback: Unsplash API photo search
  VIDEO  → Pexels API (HD stock video search)
  AUDIO  → Hardcoded CDN Library (SoundHelix, zero API key, instant)

All keys loaded from environment — never hardcoded.
Zero Pollinations dependency.
"""

import os, base64, random, requests
from dotenv import load_dotenv           # ← Fix 1: load .env before reading keys

# Load .env FIRST — must happen before any os.getenv() calls
# On HF Spaces the env vars are already injected, so this is a no-op there
# On localhost it reads the .env file
load_dotenv()

# ══════════════════════════════════════════════════════════════
# ENV KEYS — loaded & sanitised once at module import
# Fix 2: strip() + replace('"','') removes hidden quotes/spaces
#         that appear when .env values are copy-pasted with wrapping quotes
# ══════════════════════════════════════════════════════════════
def _clean_key(name: str, default: str = "") -> str:
    """Read env var and strip hidden whitespace / accidental quotes."""
    raw = os.getenv(name, default) or default
    return raw.strip().replace('"', "").replace("'", "")

def _build_cf_accounts() -> list:
    """Build and validate CF account list with sanitised keys."""
    accounts = []
    for i in (1, 2):
        acct_id = _clean_key(f"CF_ACCOUNT_ID_{i}")
        token   = _clean_key(f"CF_API_TOKEN_{i}")
        if acct_id and token:
            accounts.append({"account_id": acct_id, "api_token": token})
    return accounts

_CF_ACCOUNTS  = _build_cf_accounts()
_UNSPLASH_KEY = _clean_key("UNSPLASH_ACCESS_KEY")
_PEXELS_KEY   = _clean_key("PEXELS_API_KEY")

# Fix 3: Detailed startup debug — exact key presence + lengths
print(f"[media_generator] dotenv loaded ✅")
print(f"[media_generator] CF accounts : {len(_CF_ACCOUNTS)}"
      + (f" (ID1={_clean_key('CF_ACCOUNT_ID_1')[:6]}…)" if _CF_ACCOUNTS else " ❌ none found"))
print(f"[media_generator] Unsplash Key: {'✅ loaded' if _UNSPLASH_KEY else '❌ NOT SET'}"
      + (f" (len={len(_UNSPLASH_KEY)})" if _UNSPLASH_KEY else ""))
print(f"[media_generator] Pexels Key  : {'✅ loaded' if _PEXELS_KEY else '❌ NOT SET'}"
      + (f" (len={len(_PEXELS_KEY)})" if _PEXELS_KEY else ""))
print(f"[media_generator] Audio Engine: ✅ CDN Library (18 tracks, zero API key)")

# ══════════════════════════════════════════════════════════════
# IMAGE ENGINE
# ══════════════════════════════════════════════════════════════

def _cf_image(prompt: str) -> dict:
    """
    Try each CF account in random order (2-account rotation).
    Returns raw PNG bytes as base64 on success.
    Returns {"_cf_error": "...", "details": "..."} dict on complete failure
    (caller checks for _cf_error key, never raises).
    """
    accounts = list(_CF_ACCOUNTS)
    random.shuffle(accounts)
    last_err = "No CF accounts configured"

    for acct in accounts:
        label = acct["account_id"][:8] + "…"
        try:
            url = (
                f"https://api.cloudflare.com/client/v4/accounts/"
                f"{acct['account_id']}/ai/run/"
                f"@cf/stabilityai/stable-diffusion-xl-base-1.0"
            )
            headers = {
                "Authorization": f"Bearer {acct['api_token']}",
                "Content-Type":  "application/json",
            }
            payload = {"prompt": prompt, "num_steps": 20}
            print(f"  CF [{label}] → POST request")
            res = requests.post(url, headers=headers, json=payload, timeout=60)
            print(f"  CF [{label}] → HTTP {res.status_code}")

            if res.status_code == 200:
                return {
                    "b64":    base64.b64encode(res.content).decode("utf-8"),
                    "mime":   "image/png",
                    "url":    None,
                    "source": "cloudflare",
                }
            elif res.status_code == 401:
                last_err = f"CF [{label}]: 401 Unauthorized — check CF_API_TOKEN_{accounts.index(acct)+1}"
                print(f"  ❌ {last_err}")
            elif res.status_code == 403:
                last_err = f"CF [{label}]: 403 Forbidden — check account ID or model access"
                print(f"  ❌ {last_err}")
            else:
                try:    body_txt = res.json().get("errors", res.text[:200])
                except: body_txt = res.text[:200]
                last_err = f"CF [{label}]: HTTP {res.status_code} — {body_txt}"
                print(f"  ❌ {last_err}")

        except requests.exceptions.Timeout:
            last_err = f"CF [{label}]: Request timed out (60s)"
            print(f"  ❌ {last_err}")
        except Exception as e:
            last_err = f"CF [{label}]: {type(e).__name__}: {e}"
            print(f"  ❌ {last_err}")

    return {"_cf_error": "All Cloudflare accounts failed", "details": last_err}


def _unsplash_image(prompt: str) -> dict:
    """
    Unsplash fallback — returns a direct HTTPS image URL.
    Returns {"_us_error": "...", "details": "..."} on failure (never raises).
    """
    if not _UNSPLASH_KEY:
        return {"_us_error": "Unsplash key missing", "details": "UNSPLASH_ACCESS_KEY not set in .env or HF Secrets"}

    try:
        res = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": prompt, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {_UNSPLASH_KEY}"},
            timeout=10,
        )
        print(f"  Unsplash → HTTP {res.status_code}")

        if res.status_code == 401:
            return {"_us_error": "Unsplash 401 Unauthorized", "details": "Check UNSPLASH_ACCESS_KEY value"}
        if res.status_code != 200:
            return {"_us_error": f"Unsplash HTTP {res.status_code}", "details": res.text[:200]}

        results = res.json().get("results", [])
        if not results:
            return {"_us_error": "Unsplash: no results", "details": f"No photos found for prompt: '{prompt[:60]}'"}

        img_url = results[0]["urls"].get("full") or results[0]["urls"]["regular"]
        return {"url": img_url, "b64": None, "mime": "image/jpeg", "source": "unsplash"}

    except requests.exceptions.Timeout:
        return {"_us_error": "Unsplash timeout", "details": "Request timed out after 10s"}
    except Exception as e:
        return {"_us_error": f"Unsplash {type(e).__name__}", "details": str(e)}


def generate_image(prompt: str) -> dict:
    """
    Public — called by app.py /generate-media image branch.

    Flow:
      1. CF account rotation (random order) → returns _cf_error dict on fail
      2. Unsplash fallback                  → returns _us_error dict on fail
      3. Both failed → return structured error with details for debugging

    Returns:
      {type, b64, url, mime, source, prompt}   on success
      {error, details}                          on failure  ← structured, no crash
    """
    if not prompt or not prompt.strip():
        return {"error": "Prompt cannot be empty.", "details": ""}

    cf_result = None
    cf_err_details = ""

    # ── Step 1: Cloudflare (try all accounts) ──
    if _CF_ACCOUNTS:
        cf_result = _cf_image(prompt)
        if "_cf_error" in cf_result:
            cf_err_details = cf_result.get("details", "")
            print(f"  ❌ CF failed: {cf_err_details}")
            cf_result = None   # trigger Unsplash fallback
        else:
            print("  ✅ Image via Cloudflare")

    # ── Step 2: Unsplash fallback ──
    if cf_result is None:
        us_result = _unsplash_image(prompt)
        if "_us_error" in us_result:
            us_err_details = us_result.get("details", "")
            print(f"  ❌ Unsplash failed: {us_err_details}")
            # Both engines failed — return structured error with full debug info
            return {
                "error":   "Image generation failed on all engines.",
                "details": f"Cloudflare: {cf_err_details or 'no accounts configured'} | Unsplash: {us_err_details}",
            }
        print("  ✅ Image via Unsplash fallback")
        cf_result = us_result

    return {
        "type":   "image",
        "b64":    cf_result.get("b64"),
        "url":    cf_result.get("url"),
        "mime":   cf_result.get("mime", "image/png"),
        "source": cf_result.get("source", "cloudflare"),
        "prompt": prompt,
    }


# ══════════════════════════════════════════════════════════════
# VIDEO ENGINE
# ══════════════════════════════════════════════════════════════

def generate_video(prompt: str) -> dict:
    """
    Public — called by app.py /generate-media video branch.
    Searches Pexels for HD video matching the prompt.
    Prefers HD (1280×720) over SD quality files.

    Returns:
      {type, url, thumb, source, prompt}   on success
      {error, details}                      on failure  ← structured, no crash
    """
    if not prompt or not prompt.strip():
        return {"error": "Prompt cannot be empty.", "details": ""}

    if not _PEXELS_KEY:
        return {
            "error":   "Pexels API key not configured.",
            "details": "PEXELS_API_KEY not set in .env or HF Secrets. Get a free key at pexels.com/api/",
        }

    try:
        print(f"  Pexels → searching '{prompt[:50]}'")
        res = requests.get(
            "https://api.pexels.com/videos/search",
            params={"query": prompt, "per_page": 3, "size": "medium"},
            headers={"Authorization": _PEXELS_KEY},
            timeout=10,
        )
        print(f"  Pexels → HTTP {res.status_code}")

        if res.status_code == 401:
            return {
                "error":   "Pexels 401 Unauthorized.",
                "details": "Check PEXELS_API_KEY — it may be incorrect or expired.",
            }
        if res.status_code == 403:
            return {
                "error":   "Pexels 403 Forbidden.",
                "details": "API key does not have video search access.",
            }
        if res.status_code != 200:
            return {
                "error":   f"Pexels API error: HTTP {res.status_code}",
                "details": res.text[:300],
            }

        videos = res.json().get("videos", [])
        if not videos:
            return {
                "error":   "No videos found for this prompt.",
                "details": f"Try broader keywords. Searched: '{prompt[:60]}'",
            }

        video  = videos[0]
        files  = video.get("video_files", [])
        if not files:
            return {"error": "Pexels video has no downloadable files.", "details": ""}

        hd     = [f for f in files if f.get("quality") == "hd"]
        sd     = [f for f in files if f.get("quality") == "sd"]
        chosen = (hd or sd or files)[0]

        print(f"  ✅ Video via Pexels: quality={chosen.get('quality','?')}")
        return {
            "type":   "video",
            "url":    chosen["link"],
            "thumb":  video.get("image", ""),
            "source": "pexels",
            "prompt": prompt,
        }

    except requests.exceptions.Timeout:
        return {"error": "Pexels request timed out.", "details": "Try again — Pexels was slow to respond."}
    except Exception as e:
        return {"error": f"Video search failed: {type(e).__name__}", "details": str(e)}


# ══════════════════════════════════════════════════════════════
# AUDIO ENGINE — CDN Library
# SoundHelix royalty-free MP3s · CORS: * · zero API key
# 9 categories · 18 tracks · keyword → category routing
# ══════════════════════════════════════════════════════════════

_CDN_TRACKS = {
    "happy": [
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3", "title": "Upbeat Sunshine"},
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3", "title": "Cheerful Bounce"},
    ],
    "lofi": [
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3", "title": "Late Night Lofi"},
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3", "title": "Study Lofi Vibes"},
    ],
    "cinematic": [
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3", "title": "Cinematic Journey"},
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-6.mp3", "title": "Epic Trailer Score"},
    ],
    "nature": [
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-7.mp3", "title": "Forest Morning"},
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3", "title": "Ocean Breeze"},
    ],
    "techno": [
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3", "title": "Electronic Pulse"},
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-10.mp3", "title": "Synthwave Drive"},
    ],
    "meditation": [
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-11.mp3", "title": "Calm Meditation"},
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-12.mp3", "title": "Mindful Breathing"},
    ],
    "epic": [
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-13.mp3", "title": "Epic Battle Theme"},
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-14.mp3", "title": "Heroic Rise"},
    ],
    "jazz": [
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-15.mp3", "title": "Smooth Jazz Evening"},
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-16.mp3", "title": "Cafe Jazz"},
    ],
    "ambient": [                               # default / fallback
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3", "title": "Panda Ambient — Bamboo Dreams"},
        {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3", "title": "Panda Ambient — Forest Calm"},
    ],
}

# keyword lists → category  (first match wins, order matters)
_KEYWORD_MAP = [
    (["happy","fun","joy","upbeat","cheerful","positive","dance","party"],   "happy"),
    (["lofi","lo-fi","study","focus","chill","relax","coffee","calm study"], "lofi"),
    (["cinematic","film","movie","trailer","dramatic","emotional","story"],  "cinematic"),
    (["nature","forest","rain","ocean","birds","water","trees","outdoor"],   "nature"),
    (["techno","electronic","edm","synth","beat","club","rave","cyber"],     "techno"),
    (["meditation","meditate","yoga","breathe","mindful","peace","zen"],     "meditation"),
    (["epic","battle","war","hero","power","action","intense","thunder"],    "epic"),
    (["jazz","blues","swing","saxophone","piano","smooth","cafe","night"],   "jazz"),
]


def generate_audio(prompt: str) -> dict:
    """
    Public — called by app.py /generate-media audio branch.

    Instant — no network call, no API key, no latency.
    Keyword routing: prompt → category → random.choice(tracks)
    Falls back to 'ambient' (Panda default) if no keyword matches.

    Returns:
      {type, url, title, category, source, prompt}
    """
    if not prompt or not prompt.strip():
        return {"error": "Prompt cannot be empty."}

    q        = prompt.lower()
    category = "ambient"
    for keywords, cat in _KEYWORD_MAP:
        if any(kw in q for kw in keywords):
            category = cat
            break

    tracks = _CDN_TRACKS.get(category, _CDN_TRACKS["ambient"])
    track  = random.choice(tracks)

    print(f"  ✅ CDN Audio: category='{category}' → '{track['title']}'")
    return {
        "type":     "audio",
        "url":      track["url"],
        "title":    track["title"],
        "category": category,
        "source":   "cdn",
        "prompt":   prompt,
    }


# ══════════════════════════════════════════════════════════════
# DISPATCHER — single entry-point (optional convenience)
# app.py can call this OR call each function directly
# ══════════════════════════════════════════════════════════════
def generate_media(media_type: str, prompt: str) -> dict:
    """
    Routes to generate_image / generate_video / generate_audio.

    Args:
        media_type: "image" | "video" | "audio"
        prompt:     User creative prompt string

    Returns:
        Type-specific result dict, or {"error": "..."}
    """
    t = (media_type or "").lower().strip()
    if   t == "image": return generate_image(prompt)
    elif t == "video": return generate_video(prompt)
    elif t == "audio": return generate_audio(prompt)
    else:              return {"error": f"Unknown type: '{media_type}'. Use image, video, or audio."}


# ── Standalone smoke-test: python media_generator.py ──
if __name__ == "__main__":
    print("\n=== AUDIO (instant, no key) ===")
    for p in ["lofi chill", "epic battle", "jazz cafe", "something random"]:
        r = generate_audio(p)
        print(f"  '{p}' → {r['category']} · {r['title']}")

    print("\n=== VIDEO (needs PEXELS_API_KEY) ===")
    print(generate_video("beautiful Indian sunset timelapse"))

    print("\n=== IMAGE (needs CF or UNSPLASH key) ===")
    r = generate_image("panda in bamboo forest, photorealistic 4K")
    if "error" in r:
        print(r)
    else:
        src = r['source']
        val = (f"b64={len(r['b64'])} chars" if r.get('b64') else f"url={str(r.get('url',''))[:60]}")
        print(f"  source={src} · {val}")