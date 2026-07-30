import { useState } from "react";
import { Briefcase, Linkedin, GraduationCap, Loader2, ArrowRightLeft } from "lucide-react";
import { api } from "../../api/client.js";
import GlassCard from "../layout/GlassCard.jsx";
import MarkdownRenderer from "../generator/MarkdownRenderer.jsx";

const TONES = [
  {
    id: "professional",
    label: "Professional Tech Article",
    icon: Briefcase,
  },
  {
    id: "linkedin",
    label: "Casual LinkedIn Post",
    icon: Linkedin,
  },
  {
    id: "beginner",
    label: "Beginner-Friendly Explainer",
    icon: GraduationCap,
  },
];

export default function ToneTransformer({ content, setContent }) {
  const [activeTone, setActiveTone] = useState(null);
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleTransform(toneId) {
    setActiveTone(toneId);
    setLoading(true);
    setError("");
    setResult("");
    try {
      const { rewritten } = await api.transformTone(content, toneId);
      setResult(rewritten);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function applyToMainDraft() {
    setContent(result);
    setResult("");
    setActiveTone(null);
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
      <GlassCard>
        <h2 className="text-lg font-semibold text-white mb-1">
          🌐 Tone & Style Transformer
        </h2>
        <p className="text-sm text-slate-400 mb-4">
          Rewrite your full draft in one click, into a different tone.
        </p>
        <div className="flex flex-wrap gap-2.5">
          {TONES.map((tone) => {
            const Icon = tone.icon;
            const isActive = activeTone === tone.id;
            return (
              <button
                key={tone.id}
                onClick={() => handleTransform(tone.id)}
                disabled={loading}
                className={`btn-ghost ${
                  isActive ? "!bg-accent-500/20 !border-accent-500/40 !text-white" : ""
                }`}
              >
                {loading && isActive ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Icon size={15} />
                )}
                {tone.label}
              </button>
            );
          })}
        </div>
      </GlassCard>

      {error && (
        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
          {error}
        </p>
      )}

      {result && (
        <GlassCard>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-slate-300">
              Rewritten Draft — {TONES.find((t) => t.id === activeTone)?.label}
            </h3>
            <button className="btn-primary !py-1.5 !px-3 text-xs" onClick={applyToMainDraft}>
              <ArrowRightLeft size={13} />
              Use This Version
            </button>
          </div>
          <MarkdownRenderer content={result} />
        </GlassCard>
      )}
    </div>
  );
}
