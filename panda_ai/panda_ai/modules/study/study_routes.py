# FILE: modules/study/study_routes.py

from flask import Blueprint, request, jsonify
from user_profile import get_user_profile   # V8.3 — already exists
import requests as _req
import os

study_bp = Blueprint("study", __name__)


def _groq_key():
    return os.getenv("GROQ_API_KEY_1", "")

def _user_name() -> str:
    """Pull user's first name from V8.3 session profile. Falls back to 'Student'."""
    return get_user_profile().get("name", "Student")


@study_bp.route("/ask", methods=["POST"])
def study_ask():
    """
    POST /study/ask
    Explains a concept, answers an academic question, or debugs code.

    Request body (JSON):
      question : str   The concept, code snippet, or question to explain
      subject  : str   Optional context — "Python", "DBMS", "OS", "Java", etc.
      level    : str   "beginner" | "intermediate" | "advanced"  (default: intermediate)

    Response: { "answer": "<explanation>" }
    """
    try:
        body = request.get_json(force=True)
        question = body.get("question", "").strip()

        if not question:
            return jsonify({"error": "question is required"}), 400

        subject = f" in {body['subject']}" if body.get("subject") else ""
        level   = body.get("level", "intermediate")
        name    = _user_name()

        prompt = f"""You are an expert academic tutor helping {name}.

Topic{subject}: {question}
Level: {level}

Provide a clear, structured explanation:
- Start with a one-line definition
- Explain step by step
- Include a short code example if relevant (Python or Java preferred)
- End with one key takeaway sentence
- Keep under 400 words
- Language level appropriate for {level}"""

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
                "temperature": 0.4,
            },
            timeout=25,
        )

        if res.status_code != 200:
            return jsonify({"error": f"Groq error: HTTP {res.status_code}"}), 500

        return jsonify({"answer": res.json()["choices"][0]["message"]["content"].strip()})

    except Exception as e:
        print(f"Study ask error: {e}")
        return jsonify({"error": str(e)}), 500


@study_bp.route("/summarize", methods=["POST"])
def study_summarize():
    """
    POST /study/summarize
    Creates exam-focused study material in a chosen format.

    Request body (JSON):
      topic   : str   The topic to summarize
      subject : str   Optional — "DBMS", "OS", "Python", "Networks", etc.
      format  : str   "notes" | "bullets" | "flashcard"  (default: notes)
                        notes     → structured notes with headings
                        bullets   → max 10 concise bullet points
                        flashcard → 5 Q&A pairs for revision

    Response: { "summary": "<formatted content>" }
    """
    try:
        body  = request.get_json(force=True)
        topic = body.get("topic", "").strip()

        if not topic:
            return jsonify({"error": "topic is required"}), 400

        fmt_map = {
            "notes":     "structured notes with clear headings and subpoints",
            "bullets":   "concise bullet points — maximum 10 bullets",
            "flashcard": "Q&A flashcard format — exactly 5 questions with short answers",
        }
        fmt_instruction = fmt_map.get(body.get("format", "notes"), fmt_map["notes"])
        subject_ctx     = f" ({body['subject']})" if body.get("subject") else ""
        name            = _user_name()

        prompt = f"""Create {fmt_instruction} for: {topic}{subject_ctx}

Audience: {name} — a student preparing for exams.

Requirements:
- Accurate and exam-focused content
- Include key definitions, formulas, or commands where applicable
- Highlight the most testable points
- Maximum 450 words"""

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
                "max_tokens":  700,
                "temperature": 0.3,
            },
            timeout=25,
        )

        if res.status_code != 200:
            return jsonify({"error": f"Groq error: HTTP {res.status_code}"}), 500

        return jsonify({"summary": res.json()["choices"][0]["message"]["content"].strip()})

    except Exception as e:
        print(f"Study summarize error: {e}")
        return jsonify({"error": str(e)}), 500
