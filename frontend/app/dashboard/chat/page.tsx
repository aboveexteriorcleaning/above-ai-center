"use client";

import { useState, useRef, useEffect } from "react";
import { ChatMessage, type Message } from "@/components/chat/ChatMessage";
import { askQuestion } from "@/lib/api";

const SUGGESTIONS = [
  "What's our cash revenue this month?",
  "Which service made the most money this year?",
  "What was our CPL last month?",
  "How many jobs are scheduled this week?",
  "What's our Google rating and review count?",
  "Show me ad spend by campaign this month",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage(question: string) {
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);

    try {
      const result = await askQuestion(question);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.error || result.answer,
          result: result.error ? undefined : result,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Something went wrong: ${err instanceof Error ? err.message : "Unknown error"}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    sendMessage(q);
  }

  return (
    <div className="max-w-3xl mx-auto flex flex-col" style={{ height: "calc(100vh - 8rem)" }}>
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight" style={{ color: "#f0f1f6" }}>Chat</h1>
        <p className="text-sm mt-0.5" style={{ color: "#6b6f8a" }}>Ask anything about your business data</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {messages.length === 0 && (
          <div className="pt-4">
            <p className="text-sm mb-4" style={{ color: "#6b6f8a" }}>Try one of these:</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  disabled={loading}
                  className="text-xs rounded-full px-4 py-2 border transition-all duration-150 disabled:opacity-50"
                  style={{
                    background: "#242638",
                    borderColor: "#2e3048",
                    color: "#a0a3b8",
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLElement).style.borderColor = "#41bfec";
                    (e.currentTarget as HTMLElement).style.color = "#41bfec";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.borderColor = "#2e3048";
                    (e.currentTarget as HTMLElement).style.color = "#a0a3b8";
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}

        {loading && (
          <div className="flex">
            <div className="rounded-2xl rounded-tl-sm px-4 py-3 border" style={{ background: "#242638", borderColor: "#2e3048" }}>
              <div className="flex gap-1.5 items-center h-5">
                {[0, 150, 300].map((delay) => (
                  <span
                    key={delay}
                    className="w-1.5 h-1.5 rounded-full animate-bounce"
                    style={{ background: "#41bfec", animationDelay: `${delay}ms` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="pt-4" style={{ borderTop: "1px solid #2e3048" }}>
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about your business..."
            disabled={loading}
            className="flex-1 rounded-xl px-4 py-3 text-sm outline-none transition-all"
            style={{
              background: "#242638",
              border: "1px solid #2e3048",
              color: "#f0f1f6",
            }}
            onFocus={(e) => (e.target.style.borderColor = "#41bfec")}
            onBlur={(e) => (e.target.style.borderColor = "#2e3048")}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-5 py-3 rounded-xl text-sm font-semibold transition-all duration-150 disabled:opacity-40"
            style={{
              background: "linear-gradient(135deg, #41bfec, #2a9fd6)",
              color: "#1a1c2e",
              boxShadow: "0 4px 16px rgba(65,191,236,0.2)",
            }}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
