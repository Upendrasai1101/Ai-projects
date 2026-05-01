# --- FILE: memory.py --- V5 Stable
"""
memory.py — Panda AI V5
Auto-detects and saves user profile from conversation.
Pre-seeded with Upendrasai's confirmed profile.
Critical facts (like IPL squad corrections) always injected.
"""

import json
import re
import os

MEMORY_FILE = "memory.json"

# ── Critical facts that ALWAYS override training data ──
CRITICAL_FACTS = {
    "srh_2026_fact": "T. Natarajan is NOT in SRH squad for IPL 2026",
    "ipl_note": "Always verify IPL 2026 squad details from live search — do not use training data for squad info",
}

def load_memory():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_memory(key, value):
    mem = load_memory()
    mem[key] = value
    _write(mem)

def save_memory_bulk(data: dict):
    mem = load_memory()
    mem.update(data)
    _write(mem)

def _write(mem):
    try:
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Memory write error: {e}")

def get_memory_context():
    """
    Returns formatted memory string for Groq system prompt injection.
    Always includes critical facts regardless of stored memory.
    """
    mem = load_memory()

    # Always inject critical facts (override training data)
    mem.update(CRITICAL_FACTS)

    if not mem:
        return ""

    # Separate critical facts from user profile
    critical_keys = set(CRITICAL_FACTS.keys())
    profile_lines  = []
    critical_lines = []

    for k, v in mem.items():
        line = f"- {k.replace('_', ' ').title()}: {v}"
        if k in critical_keys:
            critical_lines.append(line)
        else:
            profile_lines.append(line)

    parts = []
    if profile_lines:
        parts.append("USER PROFILE:\n" + "\n".join(profile_lines))
    if critical_lines:
        parts.append("CRITICAL FACTS (override training data):\n" + "\n".join(critical_lines))

    return "\n\n".join(parts)

def extract_with_llm(user_message: str, groq_key: str) -> dict:
    """
    Use Groq to extract user info from message.
    Returns dict like {"name": "Ravi", "skills": "Python"}
    Empty dict if nothing found.
    """
    import requests
    try:
        prompt = f"""Extract user personal info from this message.
Return ONLY a JSON object with these optional keys:
name, role, skills, location, college, company, job_target

Message: "{user_message}"

Rules:
- Return {{}} if no personal info found
- Only extract clearly stated facts
- No guessing
- Return raw JSON only, no explanation"""

        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}",
                     "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0.1,
            },
            timeout=8,
        )
        if res.status_code != 200:
            return {}
        text = res.json()["choices"][0]["message"]["content"].strip()
        # Clean markdown fences if present
        text = text.replace("```json","").replace("```","").strip()
        data = json.loads(text)
        return {k: v for k, v in data.items() if v}
    except Exception as e:
        print(f"LLM extract error (non-fatal): {e}")
        return {}

def extract_and_save_memory(user_message: str,
                            groq_key: str,
                            save_fn):
    """
    save_fn = profile.save_user_profile (passed from app.py)
    Runs silently — never breaks main chat flow.
    Uses LLM-based extraction instead of regex patterns.
    """
    try:
        found = extract_with_llm(user_message, groq_key)
        if found:
            save_fn(found)
            print(f"Memory saved via LLM: {found}")
    except Exception as e:
        print(f"Memory extract error (non-fatal): {e}")

def clear_memory():
    try:
        if os.path.exists(MEMORY_FILE):
            # Preserve critical facts on clear
            with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(CRITICAL_FACTS, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False