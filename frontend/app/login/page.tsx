"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setError(error.message);
      setLoading(false);
    } else {
      router.push("/dashboard");
      router.refresh();
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{
        background: "linear-gradient(135deg, #1a1c2e 0%, #242638 50%, #1a1c2e 100%)",
      }}
    >
      {/* Subtle background grid */}
      <div
        className="absolute inset-0 opacity-5"
        style={{
          backgroundImage: `linear-gradient(#41bfec 1px, transparent 1px), linear-gradient(90deg, #41bfec 1px, transparent 1px)`,
          backgroundSize: "60px 60px",
        }}
      />

      <div className="relative w-full max-w-sm px-4">
        {/* Logo */}
        <div className="text-center mb-8">
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
            style={{
              background: "linear-gradient(135deg, #41bfec, #2a9fd6)",
              boxShadow: "0 8px 32px rgba(65,191,236,0.3)",
            }}
          >
            <span className="text-2xl font-bold" style={{ color: "#1a1c2e" }}>A</span>
          </div>
          <h1 className="text-2xl font-semibold" style={{ color: "#f0f1f6" }}>
            Above AI Center
          </h1>
          <p className="text-sm mt-1" style={{ color: "#6b6f8a" }}>
            Sign in to your dashboard
          </p>
        </div>

        {/* Card */}
        <div
          className="rounded-2xl p-6 border"
          style={{
            background: "#242638",
            borderColor: "#2e3048",
            boxShadow: "0 24px 48px rgba(0,0,0,0.4)",
          }}
        >
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="text-xs font-medium mb-1.5 block" style={{ color: "#a0a3b8" }}>
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="w-full rounded-xl px-4 py-2.5 text-sm outline-none transition-all"
                style={{
                  background: "#1a1c2e",
                  border: "1px solid #2e3048",
                  color: "#f0f1f6",
                }}
                onFocus={(e) => (e.target.style.borderColor = "#41bfec")}
                onBlur={(e) => (e.target.style.borderColor = "#2e3048")}
              />
            </div>

            <div>
              <label className="text-xs font-medium mb-1.5 block" style={{ color: "#a0a3b8" }}>
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                className="w-full rounded-xl px-4 py-2.5 text-sm outline-none transition-all"
                style={{
                  background: "#1a1c2e",
                  border: "1px solid #2e3048",
                  color: "#f0f1f6",
                }}
                onFocus={(e) => (e.target.style.borderColor = "#41bfec")}
                onBlur={(e) => (e.target.style.borderColor = "#2e3048")}
              />
            </div>

            {error && (
              <p className="text-xs rounded-lg px-3 py-2" style={{ color: "#ef4444", background: "rgba(239,68,68,0.1)" }}>
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all duration-150 mt-2"
              style={{
                background: loading ? "#2e3048" : "linear-gradient(135deg, #41bfec, #2a9fd6)",
                color: loading ? "#6b6f8a" : "#1a1c2e",
                boxShadow: loading ? "none" : "0 4px 16px rgba(65,191,236,0.25)",
              }}
            >
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
