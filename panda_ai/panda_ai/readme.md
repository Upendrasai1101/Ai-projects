---
title: Panda AI
emoji: 🐼
colorFrom: green
colorTo: teal
sdk: docker
pinned: false
license: mit
---

# 🐼 Panda AI — Real-Time AI Assistant

Powered by **Groq Llama 3.3 70B** with live web search via Google News RSS and Wikipedia.

## Features
- 🌐 Real-time web search (Google News RSS + Wikipedia API)
- 🔑 3-key Groq rotation for maximum free tier throughput
- 💾 2-minute smart response cache
- 🌍 Multilingual: English, Telugu, Hindi + 7 more
- 🎤 Voice input + 🔊 TTS output
- 🌙 Dark / Light theme
- 📱 Mobile responsive

## Stack
| Layer | Technology |
|-------|-----------|
| Backend | Flask + Gunicorn |
| AI Engine | Groq `llama-3.3-70b-versatile` |
| AI Fallback | OpenRouter |
| Search | Google News RSS + Wikipedia API |
| Deploy | Docker on Hugging Face Spaces |

## Developer
**Upendrasai Chaturvedula** — MCA Student  
GitHub: [Upendrasai1101/Ai-projects](https://github.com/Upendrasai1101/Ai-projects)