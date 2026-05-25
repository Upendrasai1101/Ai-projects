# FILE: charts_handler.py
# Flask Blueprint for structured data and chart generation.
# Called by app.py when Groq reply contains SHOW_CHART: trigger.
# Returns Chart.js-compatible JSON structure.

from flask import Blueprint, request, jsonify
import requests as _req
import os
import json as _json

charts_bp = Blueprint("charts", __name__)


def _groq_key():
    return os.getenv("GROQ_API_KEY_1", "")


def _build_chart_prompt(data_query):
    """
    Instructs Groq to return Chart.js-compatible JSON.
    chart_type must be bar, line, or pie.
    datasets is always an array so multi-series charts work.
    """
    return f"""You are a data visualization assistant.
The user wants a chart for: "{data_query}"

Return ONLY a valid JSON object in this exact format, nothing else:
{{
  "chart_type": "<bar|line|pie>",
  "title": "<descriptive chart title>",
  "labels": ["<label1>", "<label2>", "..."],
  "datasets": [
    {{
      "label": "<series name>",
      "data": [<number1>, <number2>, ...]
    }}
  ]
}}

Rules:
- chart_type: use bar for comparisons, line for trends, pie for percentages
- labels and data arrays must have the same length
- data values must be numbers only with no units and no symbols
- For multi-series add more objects to the datasets array
- Return raw JSON only, no explanation, no code fences, no markdown"""


@charts_bp.route("/render", methods=["POST"])
def render_chart():
    """
    POST /charts/render

    Request body:
      { "query": "Population of top 5 Indian cities" }

    Response success:
      {
        "chart_type": "bar",
        "title": "Population of Top 5 Indian Cities 2024",
        "labels": ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai"],
        "datasets": [
          {
            "label": "Population in millions",
            "data": [20.7, 32.9, 12.3, 10.5, 9.0]
          }
        ]
      }

    Response error:
      { "error": "Could not generate chart data" }
    """
    try:
        body  = request.get_json(force=True)
        query = body.get("query", "").strip()

        if not query:
            return jsonify({"error": "query is required"}), 400

        key = _groq_key()
        if not key:
            return jsonify({"error": "GROQ_API_KEY_1 not set"}), 500

        prompt = _build_chart_prompt(query)

        res = _req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       "llama-3.3-70b-versatile",
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  500,
                "temperature": 0.2,
            },
            timeout=20,
        )

        if res.status_code != 200:
            return jsonify({"error": f"Groq error: HTTP {res.status_code}"}), 500

        raw = res.json()["choices"][0]["message"]["content"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        data = _json.loads(raw)

        # Validate required fields
        for field in ["chart_type", "title", "labels", "datasets"]:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 500

        # Safe fallback for invalid chart type
        if data["chart_type"] not in ("bar", "line", "pie"):
            data["chart_type"] = "bar"

        # Validate datasets is a non-empty list
        if not isinstance(data["datasets"], list) or len(data["datasets"]) == 0:
            return jsonify({"error": "datasets must be a non-empty array"}), 500

        return jsonify(data)

    except _json.JSONDecodeError:
        return jsonify({"error": "AI returned invalid JSON for chart data"}), 500
    except Exception as e:
        print(f"Charts render error: {e}")
        return jsonify({"error": str(e)}), 500
