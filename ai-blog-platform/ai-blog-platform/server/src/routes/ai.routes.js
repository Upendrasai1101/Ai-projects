import { Router } from "express";
import { callGroq, callGroqJSON } from "../services/groq.service.js";

const router = Router();

/** Small helper so every handler doesn't repeat try/catch boilerplate */
function asyncHandler(fn) {
  return (req, res, next) => fn(req, res, next).catch(next);
}

/* ------------------------------------------------------------------ */
/* 1. AI Co-Pilot & Blog Post Generator                                */
/* ------------------------------------------------------------------ */
router.post(
  "/generate-post",
  asyncHandler(async (req, res) => {
    const { topic } = req.body;
    if (!topic || !topic.trim()) {
      return res.status(400).json({ error: "topic is required" });
    }

    const messages = [
      {
        role: "system",
        content:
          "You are a principal technical writer and blog co-pilot. " +
          "You write clear, well-structured, engaging long-form blog posts in clean Markdown. " +
          "Always include: a compelling H1 title, an intro paragraph, multiple H2/H3 sections, " +
          "a 'Key Takeaways' bulleted section, and at least one fenced code block with a language " +
          "tag when the topic is technical. Do not wrap the whole response in a code fence.",
      },
      {
        role: "user",
        content: `Write a full blog post about: "${topic}". Make it practical, current, and well organized.`,
      },
    ];

    const markdown = await callGroq(messages, {
      temperature: 0.75,
      max_tokens: 3000,
    });

    res.json({ markdown });
  })
);

/* ------------------------------------------------------------------ */
/* 2. SEO Metadata & Cover Image Generator                             */
/* ------------------------------------------------------------------ */
router.post(
  "/generate-seo",
  asyncHandler(async (req, res) => {
    const { content } = req.body;
    if (!content || !content.trim()) {
      return res.status(400).json({ error: "content is required" });
    }

    const messages = [
      {
        role: "system",
        content:
          "You are an SEO strategist. Given a blog post, return ONLY a JSON object " +
          "with keys: metaTitle (max 60 chars), metaDescription (max 160 chars), " +
          "tags (array of 6-10 lowercase keyword strings), and imagePrompts " +
          "(array of 3 short, vivid text-to-image prompts suitable for an AI image " +
          "generator or an Unsplash search query representing the article's cover image). " +
          "No prose, no markdown, JSON only.",
      },
      {
        role: "user",
        content: `Article content:\n\n${content.slice(0, 6000)}`,
      },
    ];

    const seo = await callGroqJSON(messages, { temperature: 0.5 });

    // Build ready-to-use Unsplash Source URLs from the image prompts
    const unsplashSuggestions = (seo.imagePrompts || []).map((prompt) => ({
      prompt,
      url: `https://source.unsplash.com/1600x900/?${encodeURIComponent(
        prompt
      )}`,
    }));

    res.json({ ...seo, unsplashSuggestions });
  })
);

/* ------------------------------------------------------------------ */
/* 3. Smart Executive Summary (TL;DR)                                  */
/* ------------------------------------------------------------------ */
router.post(
  "/generate-summary",
  asyncHandler(async (req, res) => {
    const { content } = req.body;
    if (!content || !content.trim()) {
      return res.status(400).json({ error: "content is required" });
    }

    const wordCount = content.trim().split(/\s+/).length;
    const readingTimeMinutes = Math.max(1, Math.round(wordCount / 200));

    const messages = [
      {
        role: "system",
        content:
          "You are an editor. Given an article, return ONLY a JSON object with a single key " +
          "'bullets': an array of EXACTLY 3 concise, high-signal executive-summary bullet points " +
          "(each under 20 words) capturing the article's most important takeaways. JSON only.",
      },
      {
        role: "user",
        content: `Article content:\n\n${content.slice(0, 6000)}`,
      },
    ];

    const { bullets } = await callGroqJSON(messages, { temperature: 0.4 });

    res.json({ bullets, wordCount, readingTimeMinutes });
  })
);

/* ------------------------------------------------------------------ */
/* 4. "Ask This Article" Interactive RAG Mini-Chatbot                  */
/* ------------------------------------------------------------------ */
router.post(
  "/ask-article",
  asyncHandler(async (req, res) => {
    const { content, question, history = [] } = req.body;
    if (!content || !question) {
      return res
        .status(400)
        .json({ error: "content and question are required" });
    }

    // Simple context-window guard: truncate very long articles.
    const trimmedContent = content.slice(0, 8000);

    const priorTurns = Array.isArray(history)
      ? history.slice(-6).map((h) => ({
          role: h.role === "assistant" ? "assistant" : "user",
          content: String(h.content).slice(0, 1000),
        }))
      : [];

    const messages = [
      {
        role: "system",
        content:
          "You are a helpful assistant embedded in a blog post. Answer the reader's question " +
          "using ONLY information contained in the ARTICLE below. If the answer is not in the " +
          "article, say clearly that the article doesn't cover that — do not make anything up. " +
          "Keep answers concise (2-5 sentences) unless the reader asks for more detail.\n\n" +
          `ARTICLE:\n"""\n${trimmedContent}\n"""`,
      },
      ...priorTurns,
      { role: "user", content: question },
    ];

    const answer = await callGroq(messages, {
      temperature: 0.3,
      max_tokens: 600,
    });

    res.json({ answer });
  })
);

/* ------------------------------------------------------------------ */
/* 5. 1-Click Tone & Style Transformer                                  */
/* ------------------------------------------------------------------ */
const TONE_PROMPTS = {
  professional:
    "Rewrite the text as a polished, authoritative professional tech article. Precise language, industry terminology where appropriate, structured paragraphs.",
  linkedin:
    "Rewrite the text as a casual, punchy LinkedIn post: short paragraphs, a hook opening line, conversational tone, tasteful emoji use, and a closing question or call-to-action.",
  beginner:
    "Rewrite the text as a beginner-friendly explainer: simple vocabulary, analogies, short sentences, and explicit definitions of any jargon.",
};

router.post(
  "/transform-tone",
  asyncHandler(async (req, res) => {
    const { content, tone } = req.body;
    if (!content || !tone) {
      return res.status(400).json({ error: "content and tone are required" });
    }
    const instruction = TONE_PROMPTS[tone];
    if (!instruction) {
      return res.status(400).json({
        error: `Unknown tone "${tone}". Valid options: ${Object.keys(
          TONE_PROMPTS
        ).join(", ")}`,
      });
    }

    const messages = [
      {
        role: "system",
        content:
          "You are a professional editor and rewriting specialist. Preserve the original " +
          "meaning and all facts, only change tone/style/structure as instructed. Return Markdown.",
      },
      {
        role: "user",
        content: `${instruction}\n\nOriginal text:\n"""\n${content.slice(
          0,
          6000
        )}\n"""`,
      },
    ];

    const rewritten = await callGroq(messages, {
      temperature: 0.6,
      max_tokens: 2500,
    });

    res.json({ rewritten });
  })
);

export default router;
