import { useState } from "react";
import {
  PenSquare,
  Sparkles,
  Clock,
  MessageCircleQuestion,
  Wand2,
} from "lucide-react";
import Navbar from "./components/layout/Navbar.jsx";
import Tabs from "./components/layout/Tabs.jsx";
import BlogGenerator from "./components/generator/BlogGenerator.jsx";
import SeoGenerator from "./components/seo/SeoGenerator.jsx";
import ExecutiveSummary from "./components/summary/ExecutiveSummary.jsx";
import AskArticleChat from "./components/chat/AskArticleChat.jsx";
import ToneTransformer from "./components/tone/ToneTransformer.jsx";

const TABS = [
  { id: "generate", label: "AI Co-Pilot", icon: PenSquare },
  { id: "seo", label: "SEO & Cover", icon: Sparkles },
  { id: "summary", label: "Executive Summary", icon: Clock },
  { id: "chat", label: "Ask This Article", icon: MessageCircleQuestion },
  { id: "tone", label: "Tone Transformer", icon: Wand2 },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("generate");
  const [content, setContent] = useState("");

  return (
    <div className="min-h-screen">
      <Navbar />

      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="mb-6">
          <Tabs tabs={TABS} active={activeTab} onChange={setActiveTab} />
        </div>

        {activeTab === "generate" && (
          <BlogGenerator content={content} setContent={setContent} />
        )}
        {activeTab === "seo" && <SeoGenerator content={content} />}
        {activeTab === "summary" && <ExecutiveSummary content={content} />}
        {activeTab === "chat" && <AskArticleChat content={content} />}
        {activeTab === "tone" && (
          <ToneTransformer content={content} setContent={setContent} />
        )}
      </main>

      <footer className="max-w-6xl mx-auto px-6 py-8 text-center text-xs text-slate-600">
        Built with React, Tailwind CSS & Groq LLaMA inference.
      </footer>
    </div>
  );
}
