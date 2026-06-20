# FILE: modules/pad/pad_routes.py

from flask import Blueprint, request, jsonify
from user_profile import get_user_id       # V8.3 session UID — already exists
import os

pad_bp  = Blueprint("pad", __name__)
PAD_DIR = "user_pads"
os.makedirs(PAD_DIR, exist_ok=True)   # auto-creates folder on first import


def _pad_path() -> str:
    """Returns this user's pad file path, scoped by session UID."""
    return os.path.join(PAD_DIR, f"{get_user_id()}.txt")


@pad_bp.route("/load", methods=["GET"])
def load_pad():
    """
    GET /pad/load
    Returns this user's saved notes as a string.
    Returns empty string if user has no saved notes yet.

    Response: { "notes": "<text>" }
    """
    try:
        path = _pad_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return jsonify({"notes": f.read()})
        return jsonify({"notes": ""})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@pad_bp.route("/save", methods=["POST"])
def save_pad():
    """
    POST /pad/save
    Overwrites this user's saved notes with the new content.
    Called by the frontend after a debounce delay (1.5s after last keystroke).

    Request body: { "notes": "<text>" }
    Response:     { "status": "saved" }
    """
    try:
        notes = request.get_json(force=True).get("notes", "")
        with open(_pad_path(), "w", encoding="utf-8") as f:
            f.write(notes)
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
