import { useState } from "react";
import { Sparkles, Loader2, Image as ImageIcon, Tag } from "lucide-react";
import { api } from "../../api/client.js";
import GlassCard from "../layout/GlassCard.jsx";

export default function SeoGenerator({ content }) {
  const [seo, setSeo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleGenerate() {
    setLoading(true);
    setError("");
    try {
      const data = await api.generateSEO(content);
      setSeo(data);
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
            🎨 SEO & Cover Image
          </h2>
          <p className="text-sm text-slate-400">
            Meta title, description, tags, and cover image ideas — generated
            from your draft.
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
            <Sparkles size={16} />
          )}
          {loading ? "Analyzing..." : "Generate SEO Metadata"}
        </button>
      </GlassCard>

      {error && (
        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
          {error}
        </p>
      )}

      {seo && (
        <div className="grid md:grid-cols-2 gap-6">
          <GlassCard>
            <h3 className="text-sm font-medium text-slate-300 mb-3">
              Meta Title
            </h3>
            <p className="text-white font-medium mb-1">{seo.metaTitle}</p>
            <p className="text-xs text-slate-500 mb-4">
              {seo.metaTitle?.length || 0}/60 chars
            </p>

            <h3 className="text-sm font-medium text-slate-300 mb-3">
              Meta Description
            </h3>
            <p className="text-slate-300 text-sm mb-1">
              {seo.metaDescription}
            </p>
            <p className="text-xs text-slate-500 mb-4">
              {seo.metaDescription?.length || 0}/160 chars
            </p>

            <h3 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-1.5">
              <Tag size={14} /> Tags & Keywords
            </h3>
            <div className="flex flex-wrap gap-2">
              {(seo.tags || []).map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-2.5 py-1 rounded-full bg-accent-500/15 text-accent-400 border border-accent-500/20"
                >
                  #{tag}
                </span>
              ))}
            </div>
          </GlassCard>

          <GlassCard>
            <h3 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-1.5">
              <ImageIcon size={14} /> Cover Image Suggestions
            </h3>
            <div className="space-y-3">
              {(seo.unsplashSuggestions || []).map((item, i) => (
                <div
                  key={i}
                  className="rounded-xl overflow-hidden border border-white/10 bg-white/5"
                >
                  <img
                    src={item.url}
                    alt={item.prompt}
                    className="w-full h-32 object-cover"
                    loading="lazy"
                  />
                  <p className="text-xs text-slate-400 p-2.5">
                    {item.prompt}
                  </p>
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-500 mt-3">
              Images are pulled live from Unsplash Source using the AI's
              suggested prompts — swap in a licensed image API for
              production use.
            </p>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
