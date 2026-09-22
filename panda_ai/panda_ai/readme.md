---
title: "Panda AI Official"
emoji: "🐼"
colorFrom: "blue"
colorTo: "indigo"
sdk: "docker"
app_file: "app.py"
pinned: false
---

<div align="center">
  <h1>🐼 Panda AI — Real-Time AI Assistant</h1>
  <p><b>Powered by Groq Llama 3.3 70B with live web search, multimodal processing, and high-availability architecture.</b></p>
  
  <p>
    <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/Flask-Framework-black?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
    <img src="https://img.shields.io/badge/Groq-API-orange?style=for-the-badge&logo=openai&logoColor=white" alt="Groq">
    <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
    <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  </p>
</div>

---

## 🚀 Overview
**Panda AI** is a production-grade, multi-user AI assistant platform built to go beyond standard text chatbots. It features real-time search grounding, multimodal file processing, and a resilient multi-provider fallback system to ensure zero-cost, high-availability deployments.

---

## ✨ Key Features

* **🌐 Real-Time Web Search:** Integrated with Google News RSS and Wikipedia API for up-to-date query grounding.
* **🔑 Multi-Key Load Balancing:** Engineered with a 3-key Groq rotation mechanism to maximize free-tier throughput and prevent rate limits.
* **📂 Multimodal Processing:** Full capability to handle and analyze documents, images, audio, and video files.
* **💾 Smart Caching:** Implements a 2-minute smart response cache to drastically lower API overhead and speed up interactions.
* **🌍 Multilingual Support:** Seamlessly communicates in English, Telugu, Hindi, and 7+ other languages.
* **🎙️ Voice & UI Controls:** Built-in voice input, Text-to-Speech (TTS) output, and toggleable Dark/Light themes.

---

## 🛠️ Tech Stack

* **Backend:** Python, Flask, REST APIs
* **AI Engine:** Groq API (Llama 3.3 70B), Prompt Engineering
* **Integration & Tools:** Docker, Git, Web Search APIs
* **Frontend:** HTML5, CSS3, JavaScript

---

## 📂 Project Architecture

```text
panda_ai/
├── modules/           # Modular tool handlers (Search, Maps, Charts)
├── static/            # Frontend assets (CSS, JavaScript)
├── user_pads/         # Multi-user session management
├── app.py             # Core Flask application and routing
├── file_processor.py  # Multimodal file handling
├── memory.py          # Context and state management
├── requirements.txt   # Project dependencies
└── Dockerfile         # Containerization configuration
