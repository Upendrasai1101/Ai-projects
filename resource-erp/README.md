<div align="center">
  <h1>🏢 Universal AI-Powered Resource & Budget ERP System</h1>
  <p><b>A multi-domain ERP built with pure Java 11+ and Groq REST API, featuring a runtime Industry Profile switcher and browser dashboard.</b></p>
  
  <p>
    <img src="https://img.shields.io/badge/Java-11%2B-orange?style=for-the-badge&logo=openjdk&logoColor=white" alt="Java">
    <img src="https://img.shields.io/badge/Groq-AI_API-blue?style=for-the-badge&logo=openai&logoColor=white" alt="Groq API">
    <img src="https://img.shields.io/badge/Architecture-Pure_Java-green?style=for-the-badge" alt="Architecture">
    <img src="https://img.shields.io/badge/License-MIT-purple?style=for-the-badge" alt="License">
  </p>
</div>

---

## 🚀 Overview
**Resource & Budget ERP System** is a production-style, multi-domain ERP built entirely with **pure Java 11+** (`java.net.http.HttpClient` / `com.sun.net.httpserver.HttpServer`, with **zero external JSON/HTTP libraries**) and the **Groq REST API**. 

One single codebase dynamically adapts to four distinct industries—*Retail/IT, Pharmacy, Construction, and Restaurant/Cloud Kitchen*—via a runtime Industry Profile switcher.

---

## ✨ Key Features

* **🌐 Multi-Domain Adaptability:** Instantly switches context across Retail, Pharmacy, Construction, and Restaurant domains with domain-grounded AI prompts.
* **📊 Advanced Budget Engine:** Tracks budget caps, daily burn rates, projected spends, cost variances, and EOQ calculations with Smart Purchase Guards.
* **🤖 Groq LLM Integration:** Powered by LLaMA models to provide intelligent business insights, anomaly detection, and automated reordering.
* **👥 Multi-User Web Dashboard:** Built-in lightweight HTTP server supporting isolated sessions, real-time inventory tracking, and animated CSS views.
* **⚡ Zero Framework Overhead:** Implemented using core JDK features with custom hand-rolled JSON parsing and zero external bloat.

---

## 🛠️ Tech Stack

* **Core Backend:** Java 11+, OOP, HttpHandler, HttpClient
* **AI Engine:** Groq REST API (LLaMA)
* **Web UI:** Plain HTML5, CSS3 (Animations), JavaScript (SPA)
* **Tools & Build:** Maven, Git

---

## 📂 Project Architecture

```text
resource-erp/
├── public/                       <- Web frontend (HTML/CSS/JS dashboard)
├── src/main/java/com/erp/
│   ├── Main.java                 <- Console entry point
│   ├── models/                   <- Resource, Transaction, IndustryProfile
│   ├── engine/                   <- InventoryEngine & BudgetEngine
│   ├── services/                 <- AIService (Groq Integration)
│   ├── utils/                    <- EnvLoader & JsonUtil
│   └── web/                      <- WebServer, ApiHandler & SessionManager
├── pom.xml
└── README.md
