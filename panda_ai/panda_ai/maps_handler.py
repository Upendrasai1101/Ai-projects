# FILE: maps_handler.py
# Flask Blueprint for map coordinate resolution.
# Called by app.py when Groq reply contains SHOW_MAP: trigger.
# No external libraries needed beyond requests (already installed).

from flask import Blueprint, request, jsonify
import requests as _req
import os
import json as _json

maps_bp = Blueprint("maps", __name__)


def _groq_key():
    return os.getenv("GROQ_API_KEY_1", "")


def _build_map_prompt(location_query):
    """
    Instructs Groq to return ONLY a JSON object with coordinates.
    Temperature 0.1 used for factual accuracy on coordinates.
    """
    return f"""You are a geocoding assistant.
The user wants to see a map of: "{location_query}"

Return ONLY a valid JSON object in this exact format, nothing else:
{{
  "lat": <latitude as float>,
  "lon": <longitude as float>,
  "zoom": <zoom level 1-18 as integer>,
  "label": "<place name as string>",
  "description": "<one sentence about this place>"
}}

Rules:
- lat and lon must be accurate real-world coordinates
- zoom: 5 for countries, 10 for cities, 14 for landmarks, 16 for streets
- label: short place name only e.g. Hyderabad India
- Return raw JSON only, no explanation, no code fences, no markdown"""


@maps_bp.route("/resolve", methods=["POST"])
def resolve_map():
    """
    POST /maps/resolve

    Request body:
      { "query": "Hyderabad" }

    Response success:
      {
        "lat": 17.3850,
        "lon": 78.4867,
        "zoom": 12,
        "label": "Hyderabad, India",
        "description": "Capital city of Telangana, India."
      }

    Response error:
      { "error": "Could not resolve location" }
    """
    try:
        body  = request.get_json(force=True)
        query = body.get("query", "").strip()

        if not query:
            return jsonify({"error": "query is required"}), 400

        key = _groq_key()
        if not key:
            return jsonify({"error": "GROQ_API_KEY_1 not set"}), 500

        prompt = _build_map_prompt(query)

        res = _req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       "llama-3.3-70b-versatile",
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  200,
                "temperature": 0.1,
            },
            timeout=15,
        )

        if res.status_code != 200:
            return jsonify({"error": f"Groq error: HTTP {res.status_code}"}), 500

        raw = res.json()["choices"][0]["message"]["content"].strip()

        # Strip markdown fences if model adds them despite instructions
        raw = raw.replace("```json", "").replace("```", "").strip()

        data = _json.loads(raw)

        # Validate required fields
        for field in ["lat", "lon", "zoom", "label"]:
            if field not in data:
                return jsonify({"error": f"Missing field from AI response: {field}"}), 500

        # Type safety
        data["lat"]  = float(data["lat"])
        data["lon"]  = float(data["lon"])
        data["zoom"] = int(data.get("zoom", 13))

        return jsonify(data)

    except _json.JSONDecodeError:
        return jsonify({"error": "AI returned invalid JSON for coordinates"}), 500
    except Exception as e:
        print(f"Maps resolve error: {e}")
        return jsonify({"error": str(e)}), 500
