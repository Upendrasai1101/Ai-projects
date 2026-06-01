# FILE: orator_handler.py
# Flask Blueprint for the Panda Orator speech and essay generator.
# Follows the same pattern as study_routes.py and mail_routes.py.
# No DB. No session state. Each generate call is fully stateless.

from flask import Blueprint, request, jsonify
import requests as _req
import os

orator_bp = Blueprint("orator", __name__)


# ── Length configuration (static mapping, no DB needed) ──────────────────────
# Each length option maps to a max_tokens budget and a word count instruction.
# These values are the only configuration needed for the three length options.

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


def _groq_key():
    return os.getenv("GROQ_API_KEY_1", "")


def _build_orator_prompt(topic, length_key, output_type):
    """
    Build the generation prompt based on topic, length, and output type.

    Args:
        topic       : str  The user-provided topic or title
        length_key  : str  One of: small, intermediate, large
        output_type : str  One of: speech, essay (derived from topic context)
                           Currently always "speech/essay" — can be split in V8.7

    Returns:
        prompt string ready to send to Groq
    """
    config    = LENGTH_CONFIG.get(length_key, LENGTH_CONFIG[DEFAULT_LENGTH])
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


# ── Main route ────────────────────────────────────────────────────────────────
@orator_bp.route("/generate", methods=["POST"])
def generate_oration():
    """
    POST /orator/generate

    Request body (JSON):
      {
        "topic":  "The Impact of Artificial Intelligence on Education",
        "length": "small" | "intermediate" | "large"
      }

    Response (success):
      {
        "text":         "<generated speech or essay text>",
        "length_label": "Small" | "Intermediate" | "Large",
        "word_hint":    "around 200 to 250 words",
        "topic":        "The Impact of Artificial Intelligence on Education"
      }

    Response (error):
      { "error": "<reason>" }
    """
    try:
        body       = request.get_json(force=True)
        topic      = body.get("topic", "").strip()
        length_raw = body.get("length", DEFAULT_LENGTH).strip().lower()

        # Validate topic
        if not topic:
            return jsonify({"error": "topic is required"}), 400

        if len(topic) > 300:
            return jsonify({"error": "topic must be 300 characters or fewer"}), 400

        # Validate and normalise length
        if length_raw not in LENGTH_CONFIG:
            length_raw = DEFAULT_LENGTH

        config = LENGTH_CONFIG[length_raw]
        prompt = _build_orator_prompt(topic, length_raw, "speech")

        key = _groq_key()
        if not key:
            return jsonify({"error": "GROQ_API_KEY_1 not set"}), 500

        res = _req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       "llama-3.3-70b-versatile",
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  config["max_tokens"],
                "temperature": 0.7,   # higher temp for creative, natural writing
            },
            timeout=30,
        )

        if res.status_code == 429:
            return jsonify({"error": "Rate limited. Please try again shortly."}), 429

        if res.status_code != 200:
            return jsonify({"error": f"Groq error: HTTP {res.status_code}"}), 500

        generated_text = res.json()["choices"][0]["message"]["content"].strip()

        if not generated_text:
            return jsonify({"error": "AI returned empty response. Please try again."}), 500

        return jsonify({
            "text":         generated_text,
            "length_label": config["label"],
            "word_hint":    config["word_hint"],
            "topic":        topic,
        })

    except Exception as e:
        print(f"Orator generate error: {e}")
        return jsonify({"error": str(e)}), 500
