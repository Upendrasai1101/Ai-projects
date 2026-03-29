# 🐯 Tiger AI

A powerful AI chat assistant with forest theme, built with Flask + Google Gemini.

![Tiger AI](https://img.shields.io/badge/AI-Tiger%20AI-green?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge)
![Gemini](https://img.shields.io/badge/Powered%20by-Gemini-orange?style=for-the-badge)

## ✨ Features
- 🌿 Beautiful Forest theme with animations
- 💬 ChatGPT-style chat history sidebar
- 💾 Chats auto-saved in browser (localStorage)
- 🐯 Powered by Google Gemini AI
- 📱 Mobile friendly

## 🚀 Setup

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/tiger-ai.git
cd tiger-ai
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Create your `.env` file
```bash
cp .env.example .env
```
Then open `.env` and add your Gemini API key:
```
GEMINI_API_KEY=your_api_key_here
```
👉 Get free API key: https://aistudio.google.com/app/apikey

### 4. Run
```bash
python app.py
```

### 5. Open browser
```
http://localhost:5000
```

## 📁 Project Structure
```
tiger-ai/
├── app.py              ← Flask backend
├── index.html          ← Frontend UI
├── requirements.txt    ← Dependencies
├── .env                ← Your API key (NOT on GitHub)
├── .env.example        ← Template for others
├── .gitignore          ← Keeps .env safe
└── README.md           ← This file
```

## ⚠️ Important
Never share your `.env` file or push it to GitHub!
