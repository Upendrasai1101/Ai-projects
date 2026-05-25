# FILE: canvas_handler.py
# Flask Blueprint for canvas image storage.
# Canvas drawing is 100% frontend in V8.5 (HTML5 Canvas + JS).
# This file receives the exported Base64 PNG and holds it in memory.
# V8.6 hook: pass stored Base64 to file_processor.extract_image() for AI vision.

from flask import Blueprint, request, jsonify
import base64
import os

canvas_bp = Blueprint("canvas", __name__)

# In-memory store: session_id -> last canvas Base64 string
# Intentionally not persisted. Cleared on server restart.
_canvas_store = {}


@canvas_bp.route("/save", methods=["POST"])
def save_canvas():
    """
    POST /canvas/save

    Receives Base64 PNG string from frontend after user clicks Send to AI.
    Stores in memory keyed by session_id.

    Request body:
      {
        "image":      "data:image/png;base64,iVBORw0KGgo...",
        "session_id": "default"
      }

    Response:
      {
        "status":    "saved",
        "message":   "Canvas received. AI vision analysis available in V8.6.",
        "size_kb":   12
      }
    """
    try:
        body       = request.get_json(force=True)
        image_b64  = body.get("image", "").strip()
        session_id = body.get("session_id", "default")

        if not image_b64:
            return jsonify({"error": "image is required"}), 400

        # Strip data URL prefix if present
        # Format: "data:image/png;base64,<actual_base64>"
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]

        # Validate it is real base64
        try:
            decoded = base64.b64decode(image_b64)
            size_kb = len(decoded) // 1024
        except Exception:
            return jsonify({"error": "Invalid base64 image data"}), 400

        # Store in memory, overwrite previous for this session
        _canvas_store[session_id] = image_b64
        print(f"Canvas saved: session={session_id}, size={size_kb}KB")

        return jsonify({
            "status":  "saved",
            "message": "Canvas received. AI vision analysis ready in V8.6.",
            "size_kb": size_kb,
        })

    except Exception as e:
        print(f"Canvas save error: {e}")
        return jsonify({"error": str(e)}), 500


@canvas_bp.route("/load", methods=["GET"])
def load_canvas():
    """
    GET /canvas/load?session_id=default

    Returns last saved canvas for this session.
    Used optionally to restore drawing after page refresh.

    Response when found:
      { "image": "data:image/png;base64,..." }

    Response when not found:
      { "image": null }
    """
    session_id = request.args.get("session_id", "default")
    image_b64  = _canvas_store.get(session_id)

    if image_b64:
        return jsonify({"image": f"data:image/png;base64,{image_b64}"})
    else:
        return jsonify({"image": None})
