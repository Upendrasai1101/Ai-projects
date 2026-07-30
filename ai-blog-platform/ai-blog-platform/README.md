# 🐼 AI-Powered Blog Platform

A production-grade, highly responsive React.js blog platform powered by
**Groq's LLaMA-class inference** — no heavy backend frameworks, just a
lightweight Express proxy protecting your API key.

![Stack](https://img.shields.io/badge/frontend-React%20%2B%20Vite%20%2B%20Tailwind-7c6df2)
![Stack](https://img.shields.io/badge/backend-Express%20(light)-2dd4bf)
![LLM](https://img.shields.io/badge/inference-Groq%20LLaMA-f472b6)

---

## ✨ Features

| # | Feature | What it does |
|---|---------|---------------|
| 1 | ✍️ **AI Co-Pilot & Blog Generator** | Turn a topic/title into a full, structured Markdown post with headings, key takeaways, and syntax-highlighted code blocks. |
| 2 | 🎨 **SEO & Cover Image Generator** | Auto meta title, meta description, SEO tags, and AI-suggested cover image prompts (wired to Unsplash Source). |
| 3 | ⏱️ **Smart Executive Summary** | Computed reading time + AI-generated 3-bullet TL;DR banner. |
| 4 | 💬 **"Ask This Article" RAG Chatbot** | Context-aware Q&A that answers strictly from the current article's content. |
| 5 | 🌐 **1-Click Tone Transformer** | Rewrite the draft as a Professional Tech Article, Casual LinkedIn Post, or Beginner-Friendly Explainer. |

---

## 🏗️ Architecture

```
ai-blog-platform/
├── server/                  # Lightweight Express API (holds the Groq key)
│   ├── src/
│   │   ├── index.js         # App entry, CORS, rate limiting
│   │   ├── routes/ai.routes.js
│   │   ├── services/groq.service.js   # Raw fetch-based Groq REST client
│   │   └── middleware/errorHandler.js
│   ├── package.json
│   └── .env.example
│
├── client/                  # Vite + React + Tailwind frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/       (Navbar, Tabs, GlassCard)
│   │   │   ├── generator/    (BlogGenerator, MarkdownRenderer)
│   │   │   ├── seo/          (SeoGenerator)
│   │   │   ├── summary/      (ExecutiveSummary)
│   │   │   ├── chat/         (AskArticleChat)
│   │   │   └── tone/         (ToneTransformer)
│   │   ├── api/client.js     # Single fetch wrapper — talks only to your backend
│   │   ├── utils/readingTime.js
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── tailwind.config.js
│   ├── vite.config.js        # Dev proxy: /api -> localhost:5000
│   └── .env.example
│
├── .gitignore
└── README.md
```

**Why this shape?** The browser never holds `GROQ_API_KEY`. Every AI call
goes: `React component → src/api/client.js → Express /api/* route →
groq.service.js → Groq REST API`. Swapping models, adding caching, or
switching providers later only touches `groq.service.js`.

---

## 🚀 Setup

### Prerequisites
- Node.js **18+** (native `fetch` is used server-side — no extra HTTP client dependency)
- A free Groq API key: https://console.groq.com/keys

### 1. Clone / unzip the project
```bash
cd ai-blog-platform
```

### 2. Backend setup
```bash
cd server
cp .env.example .env
# Open .env and paste your real GROQ_API_KEY
npm install
npm run dev
```
The API starts on **http://localhost:5000**. Verify with:
```bash
curl http://localhost:5000/api/health
```

> ⚠️ Groq periodically deprecates model IDs. If you get a "model not
> found" error, check https://console.groq.com/docs/models and update
> `GROQ_MODEL_TEXT` in `server/.env`.

### 3. Frontend setup
Open a **second terminal**:
```bash
cd client
cp .env.example .env    # optional for local dev — Vite proxies /api already
npm install
npm run dev
```
The app starts on **http://localhost:5173**.

### 4. Open the app
Visit **http://localhost:5173**, enter a topic in the AI Co-Pilot tab, and
generate your first post. Then explore the SEO, Summary, Chat, and Tone
tabs — they all operate on that same draft.

---

## 🔐 Security Notes

- `GROQ_API_KEY` lives **only** in `server/.env`, never sent to the browser.
- `.gitignore` excludes `.env`, `node_modules/`, and all build output —
  only `.env.example` files are committed.
- The Express server applies **rate limiting** (30 req/min/IP by default)
  on `/api/*` to protect your Groq quota from abuse.
- All prompts are constructed server-side; the client only ever sends
  plain text (topic, content, question, tone) — never credentials.

---

## 🧩 Extending

- **Swap image provider:** replace the Unsplash Source URL building in
  `server/src/routes/ai.routes.js` (`/generate-seo`) with a real AI image
  generation API.
- **Persist posts:** add a database layer (SQLite/Postgres) behind a new
  `/api/posts` route — the frontend's `api/client.js` is already the single
  seam to extend.
- **Streaming responses:** Groq supports streaming; switch `callGroq` in
  `groq.service.js` to consume `stream: true` and pipe chunks via SSE if
  you want token-by-token rendering.

---

## 📦 Production Build

```bash
# Frontend
cd client
npm run build       # outputs to client/dist
npm run preview     # sanity-check the production build locally

# Backend
cd server
NODE_ENV=production npm start
```

Deploy `client/dist` as a static site (Vercel/Netlify/Nginx) and `server/`
as a small Node service (Render/Railway/Fly.io/EC2), pointing
`VITE_API_BASE_URL` at your deployed backend's URL and `CLIENT_ORIGIN` at
your deployed frontend's URL.

---

Built to showcase a clean, modular full-stack architecture — light backend,
fast LLM inference via Groq, and a polished glassmorphic React UI.
