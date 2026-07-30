import { Sparkles, Github } from "lucide-react";

export default function Navbar() {
  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-surface-950/70 backdrop-blur-xl">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-accent-400 to-glow-teal flex items-center justify-center shadow-glow">
            <Sparkles size={18} className="text-white" />
          </div>
          <div>
            <h1 className="font-semibold text-white leading-none">
              AI Blog Platform
            </h1>
            <p className="text-xs text-slate-500 leading-none mt-1">
              Powered by Groq · LLaMA inference
            </p>
          </div>
        </div>

        <a
          href="https://github.com"
          target="_blank"
          rel="noreferrer"
          className="btn-ghost !py-2"
        >
          <Github size={16} />
          <span className="hidden sm:inline">Source</span>
        </a>
      </div>
    </header>
  );
}
