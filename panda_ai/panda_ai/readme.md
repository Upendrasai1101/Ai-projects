---
title: Panda AI
emoji: 🐼
colorFrom: green
colorTo: teal
sdk: docker
pinned: false
license: mit
---

# 🐼 Panda AI

**Panda AI** — A real-time AI assistant powered by Groq (Llama 3.3 70B) with live web search via Google News RSS and Wikipedia.

## Features
- 🌐 Real-time web search (Google News RSS + Wikipedia)
- 🔑 3-key Groq rotation for maximum free tier limits
- 🌍 Multilingual: English, Telugu, Hindi
- 💾 2-minute smart cache
- 🎤 Voice input + 🔊 TTS output
- 🌙 Dark / Light theme

## Stack
- **Backend**: Flask + Gunicorn
- **AI**: Groq `llama-3.3-70b-versatile` + OpenRouter fallback
- **Search**: Google News RSS (feedparser) + Wikipedia API
- **Deploy**: Docker on Hugging Face Spaces

## Environment Variables (Secrets)
| Key | Description |
|-----|-------------|
| `GROQ_API_KEY_1` | Groq API key 1 |
| `GROQ_API_KEY_2` | Groq API key 2 |
| `GROQ_API_KEY_3` | Groq API key 3 |
| `OPENROUTER_API_KEY` | OpenRouter fallback (optional) |

## Developer
**Upendrasai Chaturvedula** — MCA Student