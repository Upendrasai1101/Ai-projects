# FILE: orator_handler.py (Reference/Template)
# ═══════════════════════════════════════════════════════════════════════════════
# Flask Blueprint for Panda Orator - Speech and Essay Generation
#
# Features:
#   - Stateless API (no database, no session state)
#   - Three configurable length options (small, intermediate, large)
#   - Groq API integration (llama-3.3-70b-versatile model)
#   - Full error handling and validation
#   - Rate limiting response handling
#
# Integration:
#   in app.py: from orator_handler import orator_bp
#             app.register_blueprint(orator_bp, url_prefix="/orator")
#
# Frontend:
#   POST /orator/generate with JSON body:
#   {
#     "topic": "The Impact of AI on Education",
#     "length": "small" | "intermediate" | "large"
#   }
# ═══════════════════════════════════════════════════════════════════════════════

from flask import Blueprint, request, jsonify
import requests as _req
import os

# ────────────────────────────────────────────────────────────────────────────────
# Blueprint Definition
# ────────────────────────────────────────────────────────────────────────────────

orator_bp = Blueprint("orator", __name__)

"""
The blueprint name must be "orator" and the variable must be named "orator_bp"
for proper registration in app.py:
    from orator_handler import orator_bp
    app.register_blueprint(orator_bp, url_prefix="/orator")
"""


# ────────────────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────────────────

LENGTH_CONFIG = {
    "small": {
        "max_tokens": 400,
        "word_hint":  "around 200 to 250 words",
        "label":      "Small",
    },
    "intermediate": {
        "max_tokens": 800,
        "word_hint":  "around 450 to 500 words",
        "label":      "Intermediate",
    },
    "large": {
        "max_tokens": 1500,
        "word_hint":  "around 900 to 1000 words",
        "label":      "Large",
    },
}

DEFAULT_LENGTH = "intermediate"


# ────────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ────────────────────────────────────────────────────────────────────────────────

def _groq_key():
    """Retrieve Groq API key from environment."""
    return os.getenv("GROQ_API_KEY_1", "")


def _build_orator_prompt(topic, length_key, output_type="speech"):
    """
    Build a detailed system prompt for speech/essay generation.
    
    Args:
        topic (str):       User's topic or title
        length_key (str):  "small", "intermediate", or "large"
        output_type (str): "speech" or "essay" (informational only)
    
    Returns:
        str: Complete prompt ready for Groq API
    """
    config = LENGTH_CONFIG.get(length_key, LENGTH_CONFIG[DEFAULT_LENGTH])
    word_hint = config["word_hint"]

    return f"""You are an expert speechwriter and academic writer.

Task: Write a well-structured, professional speech or essay on the following topic.

Topic: {topic}

Requirements:
- Length: {word_hint}
- Structure: Opening hook, main body with 2-3 key points, strong conclusion
- Tone: Formal, confident, and engaging
- Language: Clear and eloquent, suitable for public speaking or academic submission
- Do NOT include any meta commentary, preamble, or notes about the content
- Do NOT say "Here is your speech" or similar lead-in phrases
- Output the speech or essay text directly, starting from the first sentence
- Use paragraph breaks for readability"""


# ────────────────────────────────────────────────────────────────────────────────
# API Route
# ────────────────────────────────────────────────────────────────────────────────

@orator_bp.route("/generate", methods=["POST"])
def generate_oration():
    """
    Generate a speech or essay using Groq API.
    
    HTTP Method:  POST
    Route:        /orator/generate
    
    Request Body (JSON):
    {
      "topic": "string (required, max 300 chars)",
      "length": "small|intermediate|large (optional, defaults to intermediate)"
    }
    
    Response (200 OK):
    {
      "text": "Generated speech/essay text",
      "length_label": "Small|Intermediate|Large",
      "word_hint": "around 200 to 250 words",
      "topic": "The Impact of Artificial Intelligence on Education"
    }
    
    Response (400 Bad Request):
    {
      "error": "topic is required" | "topic must be 300 characters or fewer"
    }
    
    Response (429 Too Many Requests):
    {
      "error": "Rate limited. Please try again shortly."
    }
    
    Response (500 Internal Server Error):
    {
      "error": "GROQ_API_KEY_1 not set" | "Groq error: HTTP 5XX" | "..."
    }
    """
    try:
        # ── Parse request ──
        body = request.get_json(force=True)
        topic = body.get("topic", "").strip()
        length_raw = body.get("length", DEFAULT_LENGTH).strip().lower()

        # ── Validate topic ──
        if not topic:
            return jsonify({"error": "topic is required"}), 400

        if len(topic) > 300:
            return jsonify({"error": "topic must be 300 characters or fewer"}), 400

        # ── Validate and normalize length ──
        if length_raw not in LENGTH_CONFIG:
            length_raw = DEFAULT_LENGTH

        config = LENGTH_CONFIG[length_raw]

        # ── Build prompt ──
        prompt = _build_orator_prompt(topic, length_raw, "speech")

        # ── Get API key ──
        key = _groq_key()
        if not key:
            return jsonify({"error": "GROQ_API_KEY_1 not set"}), 500

        # ── Call Groq API ──
        res = _req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": config["max_tokens"],
                "temperature": 0.7,  # Creative writing
            },
            timeout=30,
        )

        # ── Handle rate limiting ──
        if res.status_code == 429:
            return jsonify({"error": "Rate limited. Please try again shortly."}), 429

        # ── Handle other errors ──
        if res.status_code != 200:
            return jsonify({"error": f"Groq error: HTTP {res.status_code}"}), 500

        # ── Extract response ──
        generated_text = res.json()["choices"][0]["message"]["content"].strip()

        if not generated_text:
            return jsonify({"error": "AI returned empty response. Please try again."}), 500

        # ── Return success ──
        return jsonify({
            "text": generated_text,
            "length_label": config["label"],
            "word_hint": config["word_hint"],
            "topic": topic,
        })

    except Exception as e:
        print(f"Orator generate error: {e}")
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════════════════════
# End of orator_handler.py
# ════════════════════════════════════════════════════════════════════════════════
