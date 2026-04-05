"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

interface GoogleRow {
  metric_date: string;
  calls: number;
  website_clicks: number;
  direction_requests: number;
}

export function GoogleMetricsChart({ data }: { data: GoogleRow[] }) {
  if (!data || data.length === 0) {
    return <p className="text-zinc-500 text-sm text-center py-8">No Google metrics data available</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis dataKey="metric_date" tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} width={32} />
        <Tooltip
          contentStyle={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 6 }}
          labelStyle={{ color: "#a1a1aa" }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: "#71717a" }} />
        <Line type="monotone" dataKey="calls" stroke="#3b82f6" strokeWidth={2} dot={false} name="Calls" />
        <Line type="monotone" dataKey="website_clicks" stroke="#10b981" strokeWidth={2} dot={false} name="Website Clicks" />
        <Line type="monotone" dataKey="direction_requests" stroke="#f59e0b" strokeWidth={2} dot={false} name="Directions" />
      </LineChart>
    </ResponsiveContainer>
  );
}
