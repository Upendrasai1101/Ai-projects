/**
 * Groq REST Client Helper
 * ------------------------------------------------------------------
 * Thin wrapper around Groq's OpenAI-compatible /chat/completions
 * endpoint. No SDK dependency — just fetch (native in Node >= 18).
 * Keeping this isolated means swapping models or providers later
 * only touches this one file.
 * ------------------------------------------------------------------
 */

const GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions";

function getApiKey() {
  const key = process.env.GROQ_API_KEY;
  if (!key) {
    throw new Error(
      "GROQ_API_KEY is not set. Add it to server/.env (see .env.example)."
    );
  }
  return key;
}

function getModel() {
  return process.env.GROQ_MODEL_TEXT || "openai/gpt-oss-20b";
}

/**
 * Calls Groq chat completions.
 * @param {Array<{role: string, content: string}>} messages
 * @param {Object} [options]
 * @param {number} [options.temperature=0.7]
 * @param {number} [options.max_tokens=2048]
 * @param {boolean} [options.json=false] - request strict JSON output
 * @returns {Promise<string>} raw text content of the model's reply
 */
export async function callGroq(messages, options = {}) {
  const {
    temperature = 0.7,
    max_tokens = 2048,
    json = false,
  } = options;

  const body = {
    model: getModel(),
    messages,
    temperature,
    max_tokens,
    ...(json ? { response_format: { type: "json_object" } } : {}),
  };

  const res = await fetch(GROQ_BASE_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getApiKey()}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new Error(
      `Groq API error (${res.status}): ${errText || res.statusText}`
    );
  }

  const data = await res.json();
  const content = data?.choices?.[0]?.message?.content;

  if (!content) {
    throw new Error("Groq API returned an empty response.");
  }

  return content;
}

/**
 * Convenience helper: calls Groq and parses the reply as JSON.
 * Strips markdown code fences defensively in case the model
 * wraps JSON in ```json ... ``` despite instructions.
 */
export async function callGroqJSON(messages, options = {}) {
  const raw = await callGroq(messages, { ...options, json: true });
  const cleaned = raw.replace(/```json|```/g, "").trim();
  try {
    return JSON.parse(cleaned);
  } catch (err) {
    throw new Error(
      `Failed to parse Groq JSON response: ${err.message}\nRaw: ${cleaned.slice(
        0,
        300
      )}`
    );
  }
}
