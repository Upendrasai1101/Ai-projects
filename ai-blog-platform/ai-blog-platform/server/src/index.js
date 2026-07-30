import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import rateLimit from "express-rate-limit";
import aiRoutes from "./routes/ai.routes.js";
import { errorHandler } from "./middleware/errorHandler.js";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;
const CLIENT_ORIGIN = process.env.CLIENT_ORIGIN || "http://localhost:5173";

// ---- Core middleware ----
app.use(
  cors({
    origin: CLIENT_ORIGIN.split(",").map((s) => s.trim()),
  })
);
app.use(express.json({ limit: "2mb" }));

// ---- Rate limiting (protects your Groq quota from abuse) ----
const limiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 30, // 30 requests per minute per IP
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many requests. Please slow down." },
});
app.use("/api/", limiter);

// ---- Health check ----
app.get("/api/health", (req, res) => {
  res.json({ status: "ok", model: process.env.GROQ_MODEL_TEXT || "unset" });
});

// ---- Feature routes ----
app.use("/api", aiRoutes);

// ---- 404 ----
app.use((req, res) => {
  res.status(404).json({ error: "Not found" });
});

// ---- Error handler (must be last) ----
app.use(errorHandler);

app.listen(PORT, () => {
  console.log(`✅ AI Blog Platform server running on http://localhost:${PORT}`);
});
