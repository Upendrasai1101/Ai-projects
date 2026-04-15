# --- FILE: memory.py ---
"""
memory.py — Panda AI V5 Memory System
Auto-detects and saves user profile from conversation.
Stores in memory.json (persistent across sessions).
"""

import json
import re
import os

MEMORY_FILE = "memory.json"

# ── Load memory ──
def load_memory():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

# ── Save memory ──
def save_memory(key, value):
    mem = load_memory()
    mem[key] = value
    try:
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Memory save error: {e}")

# ── Save multiple keys ──
def save_memory_bulk(data: dict):
    mem = load_memory()
    mem.update(data)
    try:
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Memory bulk save error: {e}")

# ── Get memory as context string for Groq ──
def get_memory_context():
    mem = load_memory()
    if not mem:
        return ""
    lines = [f"- {k.replace('_',' ').title()}: {v}" for k, v in mem.items()]
    return "USER MEMORY (from past conversations):\n" + "\n".join(lines)

# ── Auto-extract memory from user message ──
def extract_and_save_memory(user_message: str):
    """
    Auto-detect user info from conversation and save.
    Called silently — never breaks main chat flow.
    """
    try:
        msg = user_message.strip()
        patterns = [
            # Name
            (r'\bmy name is ([A-Za-z]+)',          'name'),
            (r'\bi am ([A-Za-z]+)\b',              'name'),
            (r'\bcall me ([A-Za-z]+)',              'name'),
            (r'\bnenu ([A-Za-z]+)\b',              'name'),
            # Role
            (r'\bi am an? ([a-z ]+ student)',      'role'),
            (r'\bi am an? ([a-z ]+ developer)',    'role'),
            (r'\bi am an? ([a-z ]+ engineer)',     'role'),
            (r'\bi work as an? ([a-z ]+)',         'role'),
            (r'\bnenu ([a-z]+ student)',            'role'),
            # Location
            (r'\bi live in ([A-Za-z ]+)',          'location'),
            (r'\bi am from ([A-Za-z ]+)',          'location'),
            (r'\bnenu ([A-Za-z]+) lo vuntanu',     'location'),
            # College
            (r'\bi study at ([A-Za-z ]+)',         'college'),
            (r'\bmy college is ([A-Za-z ]+)',      'college'),
            # Skills
            (r'\bi know ([A-Za-z, ]+) programming','skills'),
            (r'\bi am good at ([A-Za-z, ]+)',      'skills'),
            # Company
            (r'\bi work at ([A-Za-z ]+)',          'company'),
            (r'\bmy company is ([A-Za-z ]+)',      'company'),
        ]
        found = {}
        for pattern, key in patterns:
            match = re.search(pattern, msg, re.IGNORECASE)
            if match:
                value = match.group(1).strip().rstrip('.,!?')
                if len(value) > 1:
                    found[key] = value

        if found:
            save_memory_bulk(found)
            print(f"Memory saved: {found}")

    except Exception as e:
        print(f"Memory extract error (non-fatal): {e}")

# ── Clear all memory ──
def clear_memory():
    try:
        if os.path.exists(MEMORY_FILE):
            os.remove(MEMORY_FILE)
        return True
    except Exception:
        return False