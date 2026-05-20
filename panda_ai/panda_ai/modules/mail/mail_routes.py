# FILE: modules/mail/mail_routes.py

from flask import Blueprint, request, jsonify
import requests as _req
import os

mail_bp = Blueprint("mail", __name__)


def _groq_key():
    # Uses GROQ_API_KEY_1 — same key already set in V8.2, no new secrets needed.
    return os.getenv("GROQ_API_KEY_1", "")


@mail_bp.route("/generate", methods=["POST"])
def generate_email():
    """
    POST /mail/generate

    Request body (JSON):
      mode           : "pitch" | "draft"

      Pitch mode fields:
        sender_name    : str  e.g. "Ravi Kumar"
        sender_role    : str  e.g. "MCA Student"
        skills         : str  e.g. "Java, Spring Boot, Python"
        project_name   : str  e.g. "Panda AI"
        college        : str  e.g. "Andhra University"
        job_target     : str  e.g. "Java Developer"
        recipient_role : str  e.g. "HR Manager at Infosys"

      Draft mode fields:
        subject        : str  e.g. "Leave Application"
        context        : str  e.g. "Requesting 3 days leave"
        sender_name    : str
        tone           : str  "formal" | "semi-formal"  (default: formal)

    Response:
      { "email": "<generated text>", "mode": "pitch" | "draft" }
    """
    try:
        body = request.get_json(force=True)
        mode = body.get("mode", "draft").strip().lower()

        if mode not in ("pitch", "draft"):
            return jsonify({"error": "mode must be 'pitch' or 'draft'"}), 400

        from modules.mail.mail_prompts import build_pitch_prompt, build_draft_prompt
        prompt = build_pitch_prompt(body) if mode == "pitch" else build_draft_prompt(body)

        key = _groq_key()
        if not key:
            return jsonify({"error": "GROQ_API_KEY_1 not set"}), 500

        res = _req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json={
                "model":       "llama-3.3-70b-versatile",
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  600,
                "temperature": 0.5,
            },
            timeout=25,
        )

        if res.status_code == 429:
            return jsonify({"error": "Rate limited. Try again shortly."}), 429
        if res.status_code != 200:
            return jsonify({"error": f"Groq error: HTTP {res.status_code}"}), 500

        text = res.json()["choices"][0]["message"]["content"].strip()
        return jsonify({"email": text, "mode": mode})

    except Exception as e:
        print(f"Mail generate error: {e}")
        return jsonify({"error": str(e)}), 500
