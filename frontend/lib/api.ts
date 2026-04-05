/**
 * Fetch wrapper for FastAPI backend calls.
 * All calls go through Next.js API routes (server-side) so the
 * FASTAPI_URL and DASHBOARD_API_KEY never reach the browser.
 */

export interface QueryResult {
  answer: string;
  sql_used?: string;
  data: Record<string, unknown>[];
  chart_hint: "line_chart" | "bar_chart" | "kpi_cards" | "table" | "none";
  error?: string;
}

export async function askQuestion(question: string): Promise<QueryResult> {
  const res = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Query failed: ${res.status} ${text}`);
  }
  return res.json();
}

/** Server-side only: call FastAPI directly with the API key. */
export async function fetchDashboard(path: string): Promise<unknown> {
  const base = process.env.FASTAPI_URL;
  const key = process.env.DASHBOARD_API_KEY;
  if (!base || !key) throw new Error("FASTAPI_URL or DASHBOARD_API_KEY not set");

  const res = await fetch(`${base}${path}`, {
    headers: { "X-API-Key": key },
    next: { revalidate: 60 }, // cache for 60 seconds
  });
  if (!res.ok) throw new Error(`FastAPI ${path} returned ${res.status}`);
  return res.json();
}
