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
        <div className="bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-lg text-sm">
          {message.content}
        </div>
      </div>
    );
  }

  const result = message.result;
  return (
    <div className="flex flex-col gap-2 max-w-3xl">
      <div className="bg-zinc-800 rounded-2xl rounded-tl-sm px-4 py-3">
        <p className="text-sm text-zinc-100 whitespace-pre-wrap">{message.content}</p>

        {result && result.data && result.data.length > 0 && result.chart_hint !== "none" && (
          <ChartRenderer chartHint={result.chart_hint} data={result.data} />
        )}

        {result?.sql_used && (
          <div className="mt-3">
            <button
              onClick={() => setShowSql((v) => !v)}
              className="text-xs text-zinc-500 hover:text-zinc-400 transition-colors"
            >
              {showSql ? "Hide SQL" : "Show SQL"}
            </button>
            {showSql && (
              <pre className="mt-2 text-xs text-zinc-400 bg-zinc-900 rounded p-3 overflow-x-auto">
                {result.sql_used}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
