# user_profile.py — Session-based user profile management
# Renamed from profile.py to avoid conflict with Python's built-in profile module
import json, os
from flask import session

MEMORY_DIR = "user_memories"
os.makedirs(MEMORY_DIR, exist_ok=True)

def get_user_id():
    """Session-based unique ID — no login needed."""
    if "uid" not in session:
        import uuid
        session["uid"] = str(uuid.uuid4())
    return session["uid"]

def get_user_profile():
    """Load this user's profile. Returns {} if new user."""
    uid = get_user_id()
    path = os.path.join(MEMORY_DIR, f"{uid}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_user_profile(data: dict):
    """Save/update this user's profile."""
    uid = get_user_id()
    path = os.path.join(MEMORY_DIR, f"{uid}.json")
    existing = get_user_profile()
    existing.update(data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

def is_new_user():
    """True if user has no saved name yet."""
    profile = get_user_profile()
    return not profile.get("name")

def get_memory_context():
    """Format profile for AI system prompt."""
    profile = get_user_profile()
    if not profile:
        return ""
    lines = [f"- {k.replace('_',' ').title()}: {v}"
             for k, v in profile.items()]
    return "USER PROFILE:\n" + "\n".join(lines)
