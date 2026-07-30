# Universal AI-Powered Resource & Budget ERP System

A production-style, multi-domain ERP built with **pure Java 11+**
(`java.net.http.HttpClient` / `com.sun.net.httpserver.HttpServer`, no
external JSON/HTTP/web libraries) and the **Groq REST API**. One codebase
adapts to four industries — Retail/IT, Pharmacy, Construction, and
Restaurant/Cloud Kitchen — via a runtime Industry Profile switcher.

Two ways to run it:
- **Console app** (`com.erp.Main`) — the original terminal menu-driven ERP.
- **Web app** (`com.erp.web.WebServer`) — same engines, browser dashboard
  with CSS animations, REST API, multi-user sessions. See
  [Web Version](#web-version-browser-ui) below.

## Project Structure

```
resource-erp/
├── .env.example
├── .gitignore
├── pom.xml
├── README.md
├── public/                       <- Web frontend (served by WebServer)
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
└── src/main/java/com/erp/
    ├── Main.java                 <- Console entry point
    ├── models/
    │   ├── Resource.java
    │   ├── Transaction.java
    │   └── IndustryProfile.java
    ├── engine/
    │   ├── InventoryEngine.java
    │   └── BudgetEngine.java
    ├── services/
    │   └── AIService.java
    ├── utils/
    │   ├── EnvLoader.java
    │   └── JsonUtil.java
    └── web/                      <- Web entry point + REST API
        ├── WebServer.java
        ├── ApiHandler.java
        ├── StaticFileHandler.java
        ├── SessionManager.java
        └── AppSession.java
```

## Prerequisites

- JDK 11 or newer
- (Optional) Apache Maven 3.6+ — a plain `javac` build works too
- A free Groq API key from https://console.groq.com/keys

## 1. Configure your API key

```bash
cp .env.example .env
```

Edit `.env` and paste your key:

```
GROQ_API_KEY=your_real_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

`.env` is already listed in `.gitignore` — it will never be committed.
The app also honors a real OS environment variable of the same name if
you prefer that over a file (e.g. in CI/CD or Docker).

## 2. Compile & Run

### Option A — Maven

```bash
mvn clean package
java -cp target/resource-erp.jar com.erp.Main
```

### Option B — Plain javac (no Maven required)

```bash
# From the resource-erp/ directory
mkdir -p out
javac -d out --release 11 $(find src -name "*.java")
java -cp out com.erp.Main
```

> The app reads `.env` from the **current working directory**, so run the
> `java` command from `resource-erp/` (same folder as your `.env` file).

## 3. Using the app

1. On startup, pick your Industry Profile (Retail/IT, Pharmacy,
   Construction, or Restaurant).
2. Set your monthly/project Budget Cap and period length in days.
3. Use the numbered main menu for CRUD, stock movements, the budget
   dashboard, and all five Groq AI features.
4. Switch profiles anytime from the menu (option 19) — the AI context
   updates immediately for all subsequent prompts.

If `GROQ_API_KEY` isn't set, every AI menu option will explain that and
tell you how to fix it instead of crashing.

## Architecture Notes

- **`IndustryProfile`** — enum carrying the domain description injected
  into every Groq prompt, plus sample seed items and default units.
- **`InventoryEngine`** — CRUD, stock in/out, low-stock detection, and
  builds plain-text summaries fed to the AI service.
- **`BudgetEngine`** — budget cap tracking, daily burn rate, projected
  spend, cost variance, EOQ calculation, and the Smart Purchase Guard
  affordability check.
- **`AIService`** — builds domain-grounded prompts and calls
  `POST https://api.groq.com/openai/v1/chat/completions`
  via `HttpClient`, with a minimal hand-rolled `JsonUtil` for
  request-body escaping and response-text extraction (no external
  JSON library, per the pure-Java requirement).
- **`EnvLoader`** — reads `.env` once, lazily; real OS env vars always
  take priority over the file.

## Web Version (Browser UI)

Alongside the console app, this project now includes a **full web version** —
same engines (`InventoryEngine`, `BudgetEngine`, `AIService`), same Groq
integration, exposed over a REST API with a browser-based dashboard (CSS
animations, profile-picker cards, live budget bar, modal-based AI tools).

Built with **zero frameworks**: the server is `com.sun.net.httpserver.HttpServer`
(bundled with the JDK) and the frontend is plain HTML/CSS/JS — no Spring,
no npm, no build step.

### Run it

```bash
# Compile (same as the console app)
mkdir -p out
javac -d out --release 11 $(find src -name "*.java")   # macOS/Linux
# PowerShell: javac -d out --release 11 (Get-ChildItem -Path src -Recurse -Filter *.java).FullName

# Start the web server (reads .env the same way as the console app)
java -cp out com.erp.web.WebServer
```

Then open **http://localhost:8080** in your browser.

> Run the `java` command from the `resource-erp/` folder — the server looks
> for `.env` (for `GROQ_API_KEY`) and the `public/` folder (the frontend
> files) relative to the current working directory, exactly like the
> console app already does for `.env`.

Optional: override the port with `PORT=9090 java -cp out com.erp.web.WebServer`
(or set `PORT` in `.env`).

### How it works

- **Multi-user by design** — every browser tab that starts a session gets
  its own isolated `AppSession` (inventory + budget + AI context), tracked
  in-memory by `SessionManager` and referenced via a `sessionId` the
  frontend passes on every request. Multiple people can use the same
  running server with completely separate inventories.
- **`ApiHandler`** — one handler, manual path/method routing, no framework.
  Routes: `/api/profiles`, `/api/session`, `/api/profile/switch`,
  `/api/resources` (+ `/stock-in`, `/stock-out`), `/api/transactions`,
  `/api/lowstock`, `/api/stats`, `/api/budget` (+ `/purchase`, `/eoq`),
  and `/api/ai/*` for all five Groq AI features.
- **`StaticFileHandler`** — serves `public/index.html`, `public/css/style.css`,
  and `public/js/app.js` for everything else.
- **Frontend** — a single-page app: profile selection → budget setup →
  tabbed dashboard (Resources / Low Stock / Transactions / Budget / AI Tools),
  with CSS transitions/animations throughout (card hover-lift, modal
  pop-in, budget progress bar, loading spinner while Groq responds, toast
  notifications).


## Security

- The Groq API key is never hardcoded or logged.
- `.gitignore` excludes `.env`, `.idea/`, `target/`, `out/`, and `*.class`.
- Only `.env.example` (with placeholder values) is meant to be committed.
- The web version's `sessionId` is an in-memory random UUID, not a
  substitute for real authentication — fine for a portfolio/demo tool,
  not intended for public multi-tenant production use as-is.
