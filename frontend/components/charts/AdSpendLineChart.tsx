"use client";

import {
  ComposedChart, Line, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

interface DailyRow {
  date: string;
  spend: number;
  leads: number;
  cpl: number | null;
}

export function AdSpendLineChart({ data }: { data: DailyRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis yAxisId="left" tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} width={48} />
        <YAxis yAxisId="right" orientation="right" tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} width={48} />
        <Tooltip
          contentStyle={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 6 }}
          labelStyle={{ color: "#a1a1aa" }}
          formatter={(v: unknown, name: unknown) => {
            const label = name === "spend" ? "Spend" : name === "cpl" ? "CPL" : "Leads";
            const val = name === "spend" ? `$${Number(v).toLocaleString()}` : name === "cpl" ? `$${v}` : String(v);
            return [val, label] as [string, string];
          }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: "#71717a" }} />
        <Bar yAxisId="left" dataKey="spend" fill="#3b82f6" opacity={0.7} radius={[2, 2, 0, 0]} name="spend" />
        <Line yAxisId="right" type="monotone" dataKey="cpl" stroke="#f59e0b" strokeWidth={2} dot={false} name="cpl" />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
