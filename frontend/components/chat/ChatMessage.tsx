"use client";

import { ChartRenderer } from "@/components/charts/ChartRenderer";
import { useState } from "react";
import type { QueryResult } from "@/lib/api";

interface UserMessage {
  role: "user";
  content: string;
}

interface AssistantMessage {
  role: "assistant";
  content: string;
  result?: QueryResult;
}

export type Message = UserMessage | AssistantMessage;

export function ChatMessage({ message }: { message: Message }) {
  const [showSql, setShowSql] = useState(false);

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div
          className="rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-lg text-sm"
          style={{
            background: "linear-gradient(135deg, #41bfec, #2a9fd6)",
            color: "#1a1c2e",
            fontWeight: 500,
          }}
        >
          {message.content}
        </div>
      </div>
    );
  }

  const result = message.result;
  return (
    <div className="flex flex-col gap-2 max-w-3xl">
      <div
        className="rounded-2xl rounded-tl-sm px-4 py-3 border"
        style={{ background: "#242638", borderColor: "#2e3048" }}
      >
        <p className="text-sm whitespace-pre-wrap" style={{ color: "#e0e2f0", lineHeight: "1.6" }}>
          {message.content}
        </p>

        {result && result.data && result.data.length > 0 && result.chart_hint !== "none" && (
          <ChartRenderer chartHint={result.chart_hint} data={result.data} />
        )}

        {result?.sql_used && (
          <div className="mt-3">
            <button
              onClick={() => setShowSql((v) => !v)}
              className="text-xs transition-colors"
              style={{ color: "#4b4f6e" }}
              onMouseEnter={(e) => ((e.target as HTMLElement).style.color = "#6b6f8a")}
              onMouseLeave={(e) => ((e.target as HTMLElement).style.color = "#4b4f6e")}
            >
              {showSql ? "▲ Hide SQL" : "▼ Show SQL"}
            </button>
            {showSql && (
              <pre
                className="mt-2 text-xs rounded-xl p-3 overflow-x-auto"
                style={{ background: "#1a1c2e", color: "#6b6f8a", border: "1px solid #2e3048" }}
              >
                {result.sql_used}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
