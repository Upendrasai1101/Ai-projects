import { useEffect, useState } from "react";
import { Clock, ListChecks, Loader2 } from "lucide-react";
import { api } from "../../api/client.js";
import GlassCard from "../layout/GlassCard.jsx";
import { estimateReadingTime } from "../../utils/readingTime.js";

export default function ExecutiveSummary({ content }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const localEstimate = estimateReadingTime(content || "");

  useEffect(() => {
    setSummary(null);
  }, [content]);

  async function handleGenerate() {
    setLoading(true);
    setError("");
    try {
      const data = await api.generateSummary(content);
      setSummary(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (!content) {
    return (
      <GlassCard className="text-center py-16 text-slate-500">
        Generate a blog post first in the AI Co-Pilot tab.
      </GlassCard>
    );
  }

  return (
    <div className="space-y-6">
      <GlassCard className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">
            ⏱️ Executive Summary
          </h2>
          <p className="text-sm text-slate-400">
            Reading time + a 3-bullet TL;DR banner for the top of your post.
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={handleGenerate}
          disabled={loading}
        >
          {loading ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <ListChecks size={16} />
          )}
          {loading ? "Summarizing..." : "Generate Summary"}
        </button>
      </GlassCard>

      {error && (
        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
          {error}
        </p>
      )}

      {/* Live banner preview — this is what you'd render atop the article */}
      <GlassCard className="border-accent-500/30 bg-gradient-to-br from-accent-500/10 to-transparent">
        <div className="flex items-center gap-2 text-accent-400 text-sm font-medium mb-3">
          <Clock size={16} />
          {summary?.readingTimeMinutes ?? localEstimate.minutes} min read ·{" "}
          {summary?.wordCount ?? localEstimate.words} words
        </div>

        {summary?.bullets ? (
          <ul className="space-y-2">
            {summary.bullets.map((b, i) => (
              <li key={i} className="flex gap-2.5 text-slate-200 text-sm">
                <span className="text-accent-400 mt-0.5">•</span>
                {b}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">
            Click "Generate Summary" to produce the 3 key-takeaway bullets.
          </p>
        )}
      </GlassCard>
    </div>
  );
}
