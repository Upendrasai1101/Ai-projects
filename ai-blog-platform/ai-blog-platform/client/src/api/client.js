/**
 * Frontend API client.
 * Every AI feature calls the backend — the browser NEVER talks to
 * Groq directly and never sees GROQ_API_KEY.
 */

const BASE = import.meta.env.VITE_API_BASE_URL || "";

async function request(path, body) {
  const res = await fetch(`${BASE}/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

export const api = {
  generatePost: (topic) => request("/generate-post", { topic }),
  generateSEO: (content) => request("/generate-seo", { content }),
  generateSummary: (content) => request("/generate-summary", { content }),
  askArticle: (content, question, history) =>
    request("/ask-article", { content, question, history }),
  transformTone: (content, tone) => request("/transform-tone", { content, tone }),
};
