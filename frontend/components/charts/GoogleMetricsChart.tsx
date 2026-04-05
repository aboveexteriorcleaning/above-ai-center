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
    return (
      <div className="flex items-center justify-center h-40">
        <p className="text-sm" style={{ color: "#6b6f8a" }}>No Google metrics data available</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2e3048" vertical={false} />
        <XAxis dataKey="metric_date" tick={{ fill: "#6b6f8a", fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: "#6b6f8a", fontSize: 10 }} axisLine={false} tickLine={false} width={32} />
        <Tooltip
          contentStyle={{ background: "#242638", border: "1px solid #2e3048", borderRadius: 12, boxShadow: "0 8px 24px rgba(0,0,0,0.4)" }}
          labelStyle={{ color: "#a0a3b8", fontSize: 12 }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: "#6b6f8a" }} />
        <Line type="monotone" dataKey="calls" stroke="#41bfec" strokeWidth={2} dot={false} name="Calls" activeDot={{ r: 4 }} />
        <Line type="monotone" dataKey="website_clicks" stroke="rgba(65,191,236,0.6)" strokeWidth={2} dot={false} name="Website Clicks" activeDot={{ r: 4 }} />
        <Line type="monotone" dataKey="direction_requests" stroke="rgba(65,191,236,0.3)" strokeWidth={2} dot={false} name="Directions" activeDot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
