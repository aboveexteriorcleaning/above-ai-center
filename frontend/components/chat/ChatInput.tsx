"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface Props {
  onSend: (question: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = value.trim();
    if (!q) return;
    setValue("");
    onSend(q);
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask a question about your business..."
        disabled={disabled}
        className="bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-500 flex-1"
      />
      <Button
        type="submit"
        disabled={disabled || !value.trim()}
        className="bg-blue-600 hover:bg-blue-500 text-white px-5"
      >
        Send
      </Button>
    </form>
  );
}
