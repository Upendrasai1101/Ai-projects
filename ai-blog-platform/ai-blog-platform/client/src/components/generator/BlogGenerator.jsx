import { useState } from "react";
import { Wand2, Loader2, Copy, Check } from "lucide-react";
import { api } from "../../api/client.js";
import GlassCard from "../layout/GlassCard.jsx";
import MarkdownRenderer from "./MarkdownRenderer.jsx";

export default function BlogGenerator({ content, setContent }) {
  const [topic, setTopic] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  async function handleGenerate() {
    if (!topic.trim()) return;
    setLoading(true);
    setError("");
    try {
      const { markdown } = await api.generatePost(topic.trim());
      setContent(markdown);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="grid lg:grid-cols-[380px_1fr] gap-6">
      <GlassCard className="h-fit">
        <h2 className="text-lg font-semibold text-white mb-1">
          ✍️ AI Co-Pilot
        </h2>
        <p className="text-sm text-slate-400 mb-4">
          Give it a topic or title — get a full structured Markdown draft.
        </p>

        <label className="text-xs font-medium text-slate-400 mb-1.5 block">
          Topic / Title
        </label>
        <input
          className="glass-input w-full mb-4"
          placeholder='e.g. "Web3 vs Web2 in 2026"'
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleGenerate()}
        />

        <button
          className="btn-primary w-full justify-center"
          onClick={handleGenerate}
          disabled={loading || !topic.trim()}
        >
          {loading ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Wand2 size={16} />
          )}
          {loading ? "Generating..." : "Generate Blog Post"}
        </button>

        {error && (
          <p className="text-xs text-red-400 mt-3 bg-red-500/10 border border-red-500/20 rounded-lg p-2">
            {error}
          </p>
        )}

        <div className="mt-4 pt-4 border-t border-white/10">
          <p className="text-xs text-slate-500">
            💡 Tip: switch to the other tabs once you have a draft — SEO,
            summary, chat, and tone tools all use this content.
          </p>
        </div>
      </GlassCard>

      <GlassCard className="min-h-[420px]">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-slate-300">Preview</h3>
          {content && (
            <button className="btn-ghost !py-1.5 !px-3 text-xs" onClick={handleCopy}>
              {copied ? <Check size={14} /> : <Copy size={14} />}
              {copied ? "Copied" : "Copy Markdown"}
            </button>
          )}
        </div>

        {content ? (
          <MarkdownRenderer content={content} />
        ) : (
          <div className="flex flex-col items-center justify-center h-80 text-center text-slate-500">
            <Wand2 size={28} className="mb-3 opacity-40" />
            <p className="text-sm">
              Your generated article will appear here.
            </p>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
