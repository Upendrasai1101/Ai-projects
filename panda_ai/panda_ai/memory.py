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

def extract_and_save_memory(user_message: str):
    """
    Auto-detect user info from conversation and save silently.
    Never breaks main chat flow.
    """
    try:
        msg = user_message.strip()
        patterns = [
            (r'\bmy name is ([A-Za-z]+)',            'name'),
            (r'\bi am ([A-Za-z]+)\b',                'name'),
            (r'\bcall me ([A-Za-z]+)',                'name'),
            (r'\bnenu ([A-Za-z]+)\b',                'name'),
            (r'\bi am an? ([a-z ]+ student)',         'role'),
            (r'\bi am an? ([a-z ]+ developer)',       'role'),
            (r'\bi am an? ([a-z ]+ engineer)',        'role'),
            (r'\bi work as an? ([a-z ]+)',            'role'),
            (r'\bi live in ([A-Za-z ]+)',             'location'),
            (r'\bi am from ([A-Za-z ]+)',             'location'),
            (r'\bi study at ([A-Za-z ]+)',            'college'),
            (r'\bmy college is ([A-Za-z ]+)',         'college'),
            (r'\bi know ([A-Za-z, ]+) programming',  'skills'),
            (r'\bi am good at ([A-Za-z, ]+)',         'skills'),
            (r'\bi work at ([A-Za-z ]+)',             'company'),
            (r'\blooking for ([A-Za-z ]+) (job|role|position)', 'job_target'),
        ]
        found = {}
        for pattern, key in patterns:
            match = re.search(pattern, msg, re.IGNORECASE)
            if match:
                value = match.group(1).strip().rstrip('.,!?')
                if len(value) > 1:
                    found[key] = value

        # Never overwrite critical facts from conversation
        for key in CRITICAL_FACTS:
            found.pop(key, None)

        if found:
            save_memory_bulk(found)
            print(f"Memory saved: {found}")

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