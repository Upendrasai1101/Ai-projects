import { useRef, useState, useEffect } from "react";
import { MessageCircleQuestion, Send, Loader2, Bot, User } from "lucide-react";
import { api } from "../../api/client.js";
import GlassCard from "../layout/GlassCard.jsx";

export default function AskArticleChat({ content }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, loading]);

  async function handleSend() {
    const question = input.trim();
    if (!question || loading) return;

    const newMessages = [...messages, { role: "user", content: question }];
    setMessages(newMessages);
    setInput("");
    setLoading(true);
    setError("");

    try {
      const { answer } = await api.askArticle(content, question, newMessages);
      setMessages([...newMessages, { role: "assistant", content: answer }]);
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
    <GlassCard className="flex flex-col h-[560px]">
      <div className="flex items-center gap-2 mb-4">
        <MessageCircleQuestion size={18} className="text-accent-400" />
        <h2 className="text-lg font-semibold text-white">Ask This Article</h2>
      </div>
      <p className="text-xs text-slate-500 mb-4">
        Answers are grounded strictly in the article content above — the
        model is told not to use outside knowledge.
      </p>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-3 pr-1 mb-4"
      >
        {messages.length === 0 && (
          <div className="text-center text-slate-500 text-sm mt-16">
            Ask something like "What's the main argument of this article?"
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex gap-2.5 ${
              m.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            {m.role === "assistant" && (
              <div className="h-7 w-7 rounded-full bg-accent-500/20 flex items-center justify-center shrink-0">
                <Bot size={14} className="text-accent-400" />
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                m.role === "user"
                  ? "bg-accent-500/90 text-white rounded-br-sm"
                  : "bg-white/5 border border-white/10 text-slate-200 rounded-bl-sm"
              }`}
            >
              {m.content}
            </div>
            {m.role === "user" && (
              <div className="h-7 w-7 rounded-full bg-white/10 flex items-center justify-center shrink-0">
                <User size={14} className="text-slate-300" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-2.5 justify-start">
            <div className="h-7 w-7 rounded-full bg-accent-500/20 flex items-center justify-center shrink-0">
              <Bot size={14} className="text-accent-400" />
            </div>
            <div className="bg-white/5 border border-white/10 rounded-2xl rounded-bl-sm px-4 py-2.5">
              <Loader2 size={14} className="animate-spin text-slate-400" />
            </div>
          </div>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-2 mb-3">
          {error}
        </p>
      )}

      <div className="flex gap-2">
        <input
          className="glass-input flex-1"
          placeholder="Ask a question about this article..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
        />
        <button
          className="btn-primary !px-3.5"
          onClick={handleSend}
          disabled={loading || !input.trim()}
        >
          <Send size={16} />
        </button>
      </div>
    </GlassCard>
  );
}
